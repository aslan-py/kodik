"""Менеджер пула прокси для RPA-сбора BP-1.

Стратегия автовыбора адресов (design.md изменения
``add-rpa-collection-proxying``, решение D6): баланс провайдера
достаточен -> собственные порты (создать при нехватке); баланс
недостаточен -> свободные (бесплатные) прокси. Пул кэшируется в Redis с
TTL (ленивое обновление при обращении, без отдельной periodic-задачи).
Cooldown "сгоревшего" для конкретного источника адреса — отдельный ключ
в Redis с собственным TTL.

Любая ошибка провайдера (сеть, API, отсутствие ключа) приводит к тому,
что ``acquire()`` возвращает ``None`` — RPA-стратегии деградируют к
прямому запросу без прокси, прогон не прерывается (см. Requirement
«Отказ провайдера прокси не останавливает сбор»,
``specs/bp1/rpa-network-controls/spec.md``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from core.config import settings

from .provider import SxOrgClient, format_proxy_string

logger = logging.getLogger(__name__)

_POOL_KEY = 'bp1:proxy:pool'
# Общий (не по источнику) маркер: провайдер прокси недоступен. Ставится
# check_health() в начале прогона (add-proxy-provider-health-check),
# читается _get_pool() перед любым обращением к провайдеру.
_PROVIDER_DOWN_KEY = 'bp1:proxy:provider_down'


def canonical_host(source: str) -> str:
    """Привести источник (URL или голый домен) к каноническому hostname.

    Собственный маленький хелпер, а не импорт ``adaptive.hostname`` —
    ``network/`` не должен зависеть от ``adaptive/`` (design.md, D1/D6):
    оба RPA-контура BP-1 (``adaptive/`` и ``collectors/fedresurs_rpa/``)
    используют этот пакет, а зависимость в обратную сторону создала бы
    связанность между независимыми контурами.
    """
    candidate = source.strip().lower()
    if '//' not in candidate:
        candidate = f'//{candidate}'
    host = urlparse(candidate).hostname
    if not host:
        return source.strip().lower()
    return host[4:] if host.startswith('www.') else host


def _split_address(address: str) -> tuple[str, int] | None:
    """Разобрать ``ip:port`` в компоненты. ``None``, если формат неверный."""
    try:
        ip, port = address.rsplit(':', 1)
        return ip, int(port)
    except (ValueError, TypeError):
        return None


_UNSET: Any = object()


class ProxyPool:
    """Пул прокси-адресов с автовыбором стратегии и cooldown по источнику."""

    def __init__(
        self,
        redis_client: Any = None,
        api_key: str | None = _UNSET,
        base_url: str | None = _UNSET,
        client_factory: Callable[[], SxOrgClient] | None = None,
    ):
        self.redis = redis_client
        # Сентинел, а не None по умолчанию: вызывающий код должен иметь
        # возможность явно передать api_key=None («ключа нет»), отличимо
        # от «параметр не передан вовсе» (тогда — из settings). None и
        # «не передано» — разные вещи, в отличие от прежней реализации.
        self._api_key = (
            settings.sx_org_api_key if api_key is _UNSET else api_key
        )
        self._base_url = (
            settings.sx_org_base_url if base_url is _UNSET else base_url
        )
        self._client_factory = client_factory or self._default_client_factory

    def _default_client_factory(self) -> SxOrgClient:
        return SxOrgClient(api_key=self._api_key, base_url=self._base_url)

    def _cooldown_key(self, source_host: str, proxy_address: str) -> str:
        return f'bp1:proxy:cooldown:{source_host}:{proxy_address}'

    async def acquire(self, source_url_or_host: str) -> str | None:
        """Вернуть адрес прокси, не находящийся в cooldown для источника.

        Возвращает ``None`` (не бросает исключение), если провайдер не
        настроен, недоступен, или пул пуст.
        """
        source_host = canonical_host(source_url_or_host)
        try:
            addresses = await self._get_pool()
        except Exception as e:
            logger.warning(
                'Не удалось получить пул прокси для %s: %s', source_host, e
            )
            return None

        for address in addresses:
            if await self._in_cooldown(source_host, address):
                continue
            return address
        return None

    async def check_health(self) -> bool:
        """Один раз проверить работоспособность провайдера.

        Вызывается в начале прогона сбора (``AdaptiveRunner.run_all``), не
        на каждый запрос прокси. Выполняет ту же стратегию автовыбора, что
        и реальный ``acquire()`` (``_select_pool()``) — не только
        ``get_balance()``: реальный провайдер отдаёт "ключ валиден, баланс
        читается" (200 OK), но при этом ветка ``search_proxies()``
        (баланс ниже порога) может отдельно отказывать (см. реальный ответ
        sx.org: HTTP 400 "Insufficient funds..." именно на этом
        эндпоинте) — проверка только баланса такой отказ не поймала бы.
        Не настроен ключ — нечего проверять, считается успехом. Не бросает
        исключение — ошибка самой проверки не должна прерывать прогон.

        Returns:
            ``True`` — провайдер работает (или не настроен), ``False`` —
            недоступен (сбор в этом прогоне пойдёт без прокси).
        """
        if not self._api_key:
            return True

        try:
            addresses = await self._select_pool()
        except Exception as e:
            await self._mark_provider_down(e)
            return False

        await self._clear_provider_down()
        # Пул уже получен реальным вызовом выше — кэшируем сразу, чтобы
        # первый же acquire() в этом прогоне не повторял тот же запрос.
        if self.redis is not None and addresses:
            await self.redis.set(
                _POOL_KEY,
                json.dumps(addresses),
                ex=settings.bp1_proxy_pool_ttl_seconds,
            )
        return True

    async def _mark_provider_down(self, error: Exception) -> None:
        # Ровно одно сообщение на прогон — check_health() вызывается один
        # раз в начале run_all(), не на каждый acquire().
        logger.warning(
            'Прокси не работает: провайдер недоступен (%s) — необходимо '
            'пополнить баланс сервиса или проверить ключ. Сбор '
            'продолжается без прокси. TODO: получатель технического '
            'уведомления — settings.test_email/settings.test_tg; реальная '
            'отправка не реализована (заглушка-лог, см. design.md '
            'изменения add-proxy-provider-health-check).',
            error,
        )
        if self.redis is not None:
            await self.redis.set(
                _PROVIDER_DOWN_KEY,
                str(error)[:200],
                ex=settings.bp1_proxy_pool_ttl_seconds,
            )

    async def _clear_provider_down(self) -> None:
        if self.redis is not None:
            await self.redis.delete(_PROVIDER_DOWN_KEY)

    async def mark_blocked(
        self, source_url_or_host: str, proxy_address: str
    ) -> None:
        """Поставить адрес на cooldown для конкретного источника."""
        if self.redis is None:
            return
        source_host = canonical_host(source_url_or_host)
        await self.redis.set(
            self._cooldown_key(source_host, proxy_address),
            '1',
            ex=settings.bp1_proxy_cooldown_seconds,
        )

    async def _in_cooldown(self, source_host: str, address: str) -> bool:
        if self.redis is None:
            return False
        key = self._cooldown_key(source_host, address)
        return bool(await self.redis.get(key))

    async def _get_pool(self) -> list[str]:
        """Вернуть закэшированный (или свежевыбранный) пул адресов."""
        if self.redis is not None:
            cached = await self.redis.get(_POOL_KEY)
            if cached:
                try:
                    return json.loads(cached)
                except (TypeError, ValueError):
                    logger.warning('Повреждён кэш пула прокси, обновляю')

            if await self.redis.get(_PROVIDER_DOWN_KEY):
                # Провайдер уже отмечен неработоспособным (check_health()
                # в начале прогона) — не обращаемся к нему повторно.
                return []

        addresses = await self._select_pool()
        if self.redis is not None and addresses:
            await self.redis.set(
                _POOL_KEY,
                json.dumps(addresses),
                ex=settings.bp1_proxy_pool_ttl_seconds,
            )
        return addresses

    async def _select_pool(self) -> list[str]:
        """Стратегия автовыбора: баланс достаточен -> свои порты (создать
        при нехватке), иначе -> свободные прокси.
        """
        if not self._api_key:
            return []

        client = self._client_factory()
        try:
            size = settings.bp1_proxy_pool_size
            country = settings.bp1_proxy_country

            balance = await client.get_balance()
            if balance.balance >= settings.bp1_proxy_min_balance:
                raw_addresses = await self._own_ports(client, country, size)
            else:
                raw_addresses = await client.search_proxies(
                    country=country, limit=size
                )
        finally:
            await client.aclose()

        return [
            formatted
            for raw in raw_addresses
            if (formatted := self._format(raw)) is not None
        ]

    @staticmethod
    async def _own_ports(
        client: SxOrgClient, country: str | None, size: int
    ) -> list[str]:
        """Собственные порты провайдера, с созданием недостающих."""
        ports = await client.get_ports(
            country_name=country, status=1, per_page=size
        )
        addresses = [p.proxy for p in ports if p.proxy]

        missing = size - len(addresses)
        if missing > 0:
            created = await client.create_port(
                country_code=country or 'US',
                name='bp1_rpa_auto',
                count=missing,
            )
            for port in created:
                if await client.wait_for_port_ready(port.id) and port.proxy:
                    addresses.append(port.proxy)

        return addresses

    @staticmethod
    def _format(raw_address: str) -> str | None:
        """``ip:port`` -> строка подключения для Playwright/ProxyConfig.

        Провайдер не возвращает отдельные логин/пароль для портов и
        свободных прокси в переносимой части API (см. design.md, Non-Goals)
        — адрес используется как есть, без встраивания учётных данных.
        """
        parsed = _split_address(raw_address)
        if parsed is None:
            return None
        ip, port = parsed
        return format_proxy_string(ip, port)
