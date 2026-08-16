"""Резолвинг поискового URL для ``AdaptiveRunner``: кэш → пробинг → fallback."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus, urlencode

from ...core.cache import PROBED_URL_TTL_SECONDS
from ...schemas import ProbedUrl
from ...strategies.orchestrator import (
    _is_trusted_self_signed_domain,
    _ssl_unverified_context,
)
from ..search_probe import SearchUrlProber
from ..sources import SearchUrlTemplateRegistry, extract_host


class _ProbingMixin:
    """Методы ``AdaptiveRunner``, отвечающие за резолвинг поискового URL.

    Примешивается к ``AdaptiveRunner`` (см. ``core.py``) — использует его
    атрибуты ``_prober``, ``_cache``, ``_logger``, ``use_probing``,
    заведённые в ``AdaptiveRunner.__init__``.
    """

    @staticmethod
    def _probe_request(url: str, data: bytes | None = None) -> str:
        """Синхронный HTTP-запрос для пробинга (GET или POST).

        Общая основа для ``_default_probe_fetch`` (GET) и
        ``_default_probe_post`` (POST): единый User-Agent, таймаут и
        единая политика TLS.

        Фолбэк без верификации сертификата разрешён только для доменов из
        ``KNOWN_REGISTRY_DOMAINS`` (гос.порталы с самоподписанными
        сертификатами) — та же политика, что в
        ``strategies/orchestrator.py`` после Шага 13 плана рефакторинга
        (N11). Для остальных доменов TLS-ошибка остаётся ошибкой, и
        попытка честно помечается ``fetch_error``.
        """
        import urllib.request

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0 Safari/537.36'
                ),
                **(
                    {'Content-Type': 'application/x-www-form-urlencoded'}
                    if data is not None
                    else {}
                ),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception:
            if not _is_trusted_self_signed_domain(url):
                raise
            # Известный гос.портал с самоподписанным/недоверенным
            # сертификатом — повторяем без верификации.
            with urllib.request.urlopen(
                req, timeout=10, context=_ssl_unverified_context()
            ) as resp:
                return resp.read().decode('utf-8', errors='replace')

    @staticmethod
    def _default_probe_fetch(url: str) -> str:
        """Реальный GET-загрузчик для пробинга.

        Используется по умолчанию, чтобы пробинг не падал на заглушке
        ``NotImplementedError`` (как было раньше, когда fetch подставлялся
        только через ``bind_probe_fetch``). При недоступности / ошибке сети
        поднимает исключение, которое ``SearchUrlProber._safe_fetch``
        превращает в ``None`` (вариант помечается ``fetch_error``).
        """
        return _ProbingMixin._probe_request(url)

    @staticmethod
    def _default_probe_post(url: str, params: dict[str, str]) -> str:
        """Реальный POST-загрузчик формы поиска (Шаг 18 плана рефакторинга).

        Раньше этап формы в ``SearchUrlProber`` был заглушкой: он выполнял
        обычный GET, но результат помечался как ``search_method='POST'``.
        Теперь параметры уходят телом запроса
        (``application/x-www-form-urlencoded``) — так ищут сайты, где поиск
        реализован формой, а не query-строкой.
        """
        return _ProbingMixin._probe_request(
            url, data=urlencode(params).encode('utf-8')
        )

    @staticmethod
    def _default_looks_like(html: str) -> bool:
        """По умолчанию считаем любой непустой HTML похожим на выдачу.

        Лучше попытаться спарсить страницу, чем бездумно уйти в fallback:
        точная проверка «выдача ли это» зависит от конкретного сайта и
        выполняется в самом парсере.
        """
        return bool(html and html.strip())

    def bind_probe_fetch(
        self,
        fetch: Any,
        looks_like: Any | None = None,
        param_chain: tuple[str, ...] | None = None,
        post: Any | None = None,
    ) -> None:
        """Заменяет fetch (и опционально looks_like/post) у проубера.

        По умолчанию проубер использует ``_default_probe_fetch`` (реальный
        HTTP-загрузчик через urllib). Метод позволяет подставить другой
        загрузчик (браузер, httpx, мок в тестах) и/или свою проверку
        «похоже ли на выдачу».

        Подмена транспорта — «всё или ничего»: если ``post`` не передан
        явно, этап POST-формы отключается (помечается
        ``no_post_transport``), а не выполняется штатным urllib. Иначе
        подмена GET-загрузчика на мок/браузер оставляла бы POST-запросы
        ходить в реальную сеть мимо подставленного транспорта — тесты
        неожиданно стучались бы на живые сайты, а браузерный сценарий
        терял бы cookies/сессию на POST-этапе.
        """
        self._prober = SearchUrlProber(
            fetch=fetch,
            looks_like_search_results=looks_like,
            param_chain=param_chain,
            post=post,
        )

    def _build_fallback_url(self, source_name: str, search_param: str) -> str:
        """Строит fallback URL поиска, если пробинг не дал результата.

        Использует тот же per-source шаблон, что и базовый
        ``build_search_url`` (``hh.ru -> /search/vacancy?text=``), чтобы
        fallback не деградировал до универсального ``/search?q=`` для
        источников с известным шаблоном поиска.
        """
        host = extract_host(source_name)
        template = SearchUrlTemplateRegistry().resolve(source_name)
        return f'https://{host}{template}'.replace(
            '{q}', quote_plus(search_param)
        )

    async def _get_or_probe_url(
        self,
        source_name: str,
        search_param: str,
        target_name: str,
        redis_client: Any,
    ) -> tuple[str, ProbedUrl | None]:
        """Возвращает ``(url, probed_url)``: кэш -> пробинг -> fallback.

        1. Кэш: если probed URL для пары ``(источник, поисковый запрос)``
           уже сохранён — используем его (TTL 7 дней), пробинг не выполняем.
           Составной ключ (источник + хэш запроса) гарантирует, что у разных
           конкурентов на одном источнике будут независимые записи.
        2. Пробинг: иначе пробуем ``SearchUrlProber.probe_async`` по базовому
           шаблону источника (``{q}``) с таймаутом 10 с.
        3. Fallback: если пробинг не нашёл успешный вариант (или Redis
           недоступен / fetch не подключён) — строим URL по шаблону
           ``https://{host}{template}`` с percent-кодированным запросом.
           Fallback также пишется в кэш (как ``ProbedUrl``), чтобы повторные
           запуски той же пары не делали бесполезный пробинг заново.

        Возвращает ``(url, probed)``: ``url`` — итоговый URL для парсинга,
        ``probed`` — найденный/закэшированный ``ProbedUrl`` (или None).
        Итоговый URL берётся из ``probed.search_url``, если он есть.
        """
        fallback_url = self._build_fallback_url(source_name, search_param)

        try:
            cached = await self._cache.get_probed_url(
                source_name, search_param=search_param
            )
        except Exception as e:
            self._logger.warning(
                'Кэш probed URL недоступен (source=%s): %s',
                source_name,
                e,
            )
            cached = None
        if cached is not None:
            self._logger.info(
                'Probed URL для %s (query=%r) взят из кэша: %s',
                source_name,
                search_param,
                cached.search_url,
            )
            return cached.search_url, cached

        if not self.use_probing:
            self._logger.info(
                'Пробинг выключен (use_probing=False), fallback для %s: %s',
                source_name,
                fallback_url,
            )
            return fallback_url, None

        base_url = SearchUrlTemplateRegistry().build_base_url(source_name)
        # Подсказка от регистрации источника (Шаг 19 плана рефакторинга):
        # add-source проверяет поисковый эндпоинт и кэширует результат на
        # уровне источника. Готовый URL оттуда переиспользовать нельзя (он
        # искал нейтральный запрос, а не этого конкурента), но имя
        # query-параметра — знание об источнике, а не о конкуренте: с ним
        # первый боевой пробинг не перебирает цепочку с начала.
        prefer_param = await self._preferred_param_from_registration(
            source_name
        )
        try:
            probed = await self._prober.probe_async(
                base_url=base_url,
                search_query=search_param,
                target_name=target_name,
                prefer_param=prefer_param,
            )
        except Exception as e:
            self._logger.warning('Пробинг %s не выполнен: %s', source_name, e)
            probed = None

        if probed is None:
            self._logger.info(
                'Пробинг %s (query=%r) не дал результата — fallback: %s',
                source_name,
                search_param,
                fallback_url,
            )
            # Кэшируем fallback как ProbedUrl (без уверенности в результате),
            # чтобы следующая задача той же пары не пробовала пробинг снова.
            fallback_probed = ProbedUrl(
                source_name=source_name,
                search_url=fallback_url,
                confidence=0.0,
            )
            try:
                await self._cache.set_probed_url(
                    source_name,
                    fallback_probed,
                    ttl=PROBED_URL_TTL_SECONDS,
                    search_param=search_param,
                )
            except Exception as e:
                self._logger.warning(
                    'Не удалось сохранить fallback probed URL для %s: %s',
                    source_name,
                    e,
                )
            return fallback_url, None

        try:
            await self._cache.set_probed_url(
                source_name,
                probed,
                ttl=PROBED_URL_TTL_SECONDS,
                search_param=search_param,
            )
        except Exception as e:
            self._logger.warning(
                'Не удалось сохранить probed URL для %s: %s',
                source_name,
                e,
            )
        return probed.search_url, probed

    async def _preferred_param_from_registration(
        self, source_name: str
    ) -> str | None:
        """Имя query-параметра, найденное при регистрации источника.

        Читает source-level запись пробинга (ключ без поискового запроса),
        которую пишет ``SourceRegistrationService.register(probe_search=True)``,
        и возвращает имя параметра из неё. Возвращает ``None``, если записи
        нет, Redis недоступен или параметр не сохранён.
        """
        try:
            registered = await self._cache.get_probed_url(source_name)
        except Exception as e:
            self._logger.warning(
                'Не удалось прочитать probed URL источника %s: %s',
                source_name,
                e,
            )
            return None
        if registered is None or not registered.search_params:
            return None
        return next(iter(registered.search_params), None)
