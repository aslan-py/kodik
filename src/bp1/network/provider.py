"""Асинхронный клиент провайдера прокси SX.org.

Порт предоставленного клиента (``requests.Session``) на
``httpx.AsyncClient`` — весь конвейер сбора асинхронный, оборачивать
синхронный клиент в ``asyncio.to_thread`` незачем, когда в проекте уже
есть асинхронный HTTP-клиент (``httpx``, design.md изменения
``add-rpa-collection-proxying``, решение D2).

Переносится только API-поверхность, реально нужная стратегии автовыбора
пула (``network/pool.py``): баланс, порты, поиск свободных прокси.
Управление шаблонами прокси и справочники (страны/города/ASN) не
переносятся — сценария использования нет (design.md, Non-Goals).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


@dataclass
class ProxyPort:
    """Прокси-порт провайдера."""

    id: int
    name: str
    proxy: str
    country: str
    city: str
    status: int
    traffic_limit: int
    used_traffic: int
    created_at: str
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProxyPort:
        """Создать экземпляр из ответа API."""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            proxy=data.get('proxy', ''),
            country=data.get('country', ''),
            city=data.get('city', ''),
            status=data.get('status', 0),
            traffic_limit=data.get('traffic_limit', 0),
            used_traffic=data.get('used_traffic', 0),
            created_at=data.get('created_at', ''),
            expires_at=data.get('expires_at'),
        )


@dataclass
class UserBalance:
    """Баланс пользователя провайдера."""

    balance: float
    balance_traffic: float
    all_available_traffic: float
    prepared_traffic_balance: float
    balance_hold: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserBalance:
        """Создать экземпляр из ответа API."""
        return cls(
            balance=float(data.get('balance', 0)),
            balance_traffic=float(data.get('balance_traffic', 0)),
            all_available_traffic=float(data.get('all_available_traffic', 0)),
            prepared_traffic_balance=float(
                data.get('prepared_traffic_balance', 0)
            ),
            balance_hold=float(data.get('balance_hold', 0)),
        )


def format_proxy_string(
    ip: str,
    port: int,
    username: str | None = None,
    password: str | None = None,
    protocol: str = 'http',
) -> str:
    """Отформатировать строку подключения к прокси.

    Формат совпадает с тем, что ожидает Playwright (``proxy={'server': ...}``)
    и уже заложенным в ``fedresurs_rpa.schemas.ProxyConfig.server``.
    """
    if username and password:
        return f'{protocol}://{username}:{password}@{ip}:{port}'
    return f'{protocol}://{ip}:{port}'


class SxOrgClient:
    """Асинхронный клиент API sx.org — управление прокси-портами.

    Пример::

        client = SxOrgClient(api_key='...')
        balance = await client.get_balance()
        ports = await client.get_ports()
        await client.aclose()
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://api.sx.org',
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self._api_key = api_key
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip('/'),
            timeout=timeout,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )

    async def aclose(self) -> None:
        """Закрыть внутреннюю HTTP-сессию."""
        await self._client.aclose()

    async def __aenter__(self) -> SxOrgClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Выполнить HTTP-запрос к API с ретраями при сетевых ошибках.

        Ошибки сети/5xx/429 (``httpx.HTTPError``) — ретраятся с
        экспоненциальным бэкоффом до ``max_retries``. Остальные 4xx (401,
        403, 400 и т.п. — невалидный ключ, недостаточно средств на
        балансе, некорректный запрос) и ошибка на уровне полезной нагрузки
        ответа (``success: false``) не ретраятся: повтор того же запроса
        результат не изменит — это не транзиентная ошибка, а
        детерминированный отказ (см. реальный ответ sx.org на
        ``/v2/proxy/search`` при нулевом балансе: HTTP 400
        ``{"success": false, "message": "Insufficient funds..."}``, а не
        только 401/403).
        """
        params = dict(params or {})
        params['apiKey'] = self._api_key

        try:
            response = await self._client.request(
                method=method, url=endpoint, params=params, json=json_data
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and data.get('success') is False:
                error_msg = data.get('error', 'Unknown API error')
                raise ValueError(f'API Error: {error_msg}')

            return data

        except httpx.HTTPError as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            if status is not None and status != 429 and 400 <= status < 500:
                raise
            if retry_count < self._max_retries:
                wait_time = 2**retry_count
                logger.warning(
                    'Запрос к sx.org не удался (%s), повтор через %sс (%s/%s)',
                    e,
                    wait_time,
                    retry_count + 1,
                    self._max_retries,
                )
                await asyncio.sleep(wait_time)
                return await self._make_request(
                    method, endpoint, params, json_data, retry_count + 1
                )
            raise

    # ============================================================
    # ПОРТЫ
    # ============================================================

    async def get_ports(
        self,
        country_name: str | None = None,
        status: int | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[ProxyPort]:
        """Получить список портов с фильтрацией."""
        params: dict[str, Any] = {'page': page, 'per_page': per_page}
        if country_name:
            params['countryName'] = country_name
        if status is not None:
            params['status'] = status

        data = await self._make_request('GET', '/v2/proxy/ports', params=params)
        ports_data = data.get('message', {})
        if isinstance(ports_data, dict):
            items = ports_data.get('data') or ports_data.get('items') or []
        elif isinstance(ports_data, list):
            items = ports_data
        else:
            items = []
        return [ProxyPort.from_dict(p) for p in items]

    async def get_port_info(self, port_id: int) -> ProxyPort:
        """Получить детальную информацию о порте."""
        data = await self._make_request(
            'GET', '/v2/proxy/port-info', params={'id': port_id}
        )
        return ProxyPort.from_dict(data.get('message', {}))

    async def create_port(
        self,
        country_code: str,
        name: str,
        count: int = 1,
        ttl: int = 0,
        traffic_limit: int = 0,
    ) -> list[ProxyPort]:
        """Создать новый(е) прокси-порт(ы)."""
        payload = {
            'country_code': country_code,
            'name': name,
            'count': count,
            'ttl': ttl,
            'traffic_limit': traffic_limit,
        }
        data = await self._make_request(
            'POST', '/v2/proxy/create-port', json_data=payload
        )
        return [ProxyPort.from_dict(p) for p in data.get('data', [])]

    async def wait_for_port_ready(
        self,
        port_id: int,
        max_wait: int = 60,
        check_interval: int = 5,
    ) -> bool:
        """Дождаться готовности порта (``status == 1``)."""
        elapsed = 0
        while elapsed < max_wait:
            try:
                port = await self.get_port_info(port_id)
                if port.status == 1:
                    return True
            except Exception as e:
                logger.warning('Порт %s ещё не готов: %s', port_id, e)
            await asyncio.sleep(check_interval)
            elapsed += check_interval
        logger.error('Порт %s не готов после %sс', port_id, max_wait)
        return False

    # ============================================================
    # СВОБОДНЫЕ ПРОКСИ И БАЛАНС
    # ============================================================

    async def search_proxies(
        self, country: str | None = None, limit: int = 100
    ) -> list[str]:
        """Найти свободные (бесплатные) прокси вида ``IP:PORT``."""
        params: dict[str, Any] = {'limit': limit}
        if country:
            params['country'] = country

        data = await self._make_request(
            'GET', '/v2/proxy/search', params=params
        )
        proxies = []
        for key, value in data.items():
            if key in ('success', 'error', 'message'):
                continue
            if isinstance(value, str) and ':' in value:
                proxies.append(value)
        return proxies

    async def get_balance(self) -> UserBalance:
        """Получить баланс пользователя."""
        data = await self._make_request('GET', '/v2/user/balance')
        return UserBalance.from_dict(data)
