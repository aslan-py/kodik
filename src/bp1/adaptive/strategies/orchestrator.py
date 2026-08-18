"""
AgenticOrchestrator — оркестрация стратегий обхода с деградацией.

Иерархия: FAST → CRAWL4AI → BROWSER → WAYBACK → HITL.
При ошибке или недостаточном объёме контента происходит переход
к следующей, более "тяжёлой" стратегии.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from core.config import settings
from src.bp1.network.pool import ProxyPool
from src.bp1.network.throttle import default_throttle
from src.bp1.network.ua_rotation import get_random_user_agent

from ..hostname import KNOWN_REGISTRY_DOMAINS, try_extract_host
from ..schemas import SourceClassification, StrategyResult, StrategyType

logger = logging.getLogger(__name__)

# Минимальная длина контента, при которой стратегия считается успешной.
MIN_CONTENT_LENGTH = settings.bp1_min_content_length

# Минимальное количество ссылок (элементов данных) в HTML, при котором
# страница считается «информативной». Многие сайты (Lenta.ru, SPA-приложения)
# отдают по HTTP «пустой скелет» (JS-shell): тело больше MIN_CONTENT_LENGTH,
# но реальные данные появляются только после выполнения JS. Такая страница
# НЕ должна считаться успешной для FAST/CRAWL4AI — нужно деградировать до
# стратегии с JS-рендерингом (BROWSER/STEALTH).
MIN_LINK_COUNT_FOR_CONTENT = 3

# Стратегии, которые выполняют JavaScript (браузерные). Для них проверка
# «информативности» по ссылкам не применяется — только по длине контента.
_JS_RENDERING_STRATEGIES = (StrategyType.BROWSER, StrategyType.STEALTH)

# Стратегии, эмулирующие браузер против целевого источника (RPA-доступ,
# ТЗ BP-1) — для них применяются прокси, ротация User-Agent и задержка
# между запросами к одному хосту (design.md изменения
# add-rpa-collection-proxying, решение D4). Отдельный список от
# _JS_RENDERING_STRATEGIES: та служит другой цели (проверка
# информативности контента) и не включает CRAWL4AI. FAST и WAYBACK — не
# RPA-доступ (прямой HTTP и запрос к archive.org, а не к целевому
# источнику) и в этот список не входят.
_RPA_STRATEGIES = (
    StrategyType.CRAWL4AI,
    StrategyType.BROWSER,
    StrategyType.STEALTH,
)

# HTTP-статусы, характерные для блокировки по IP (см. Requirement «Прокси,
# заблокированный источником, не переиспользуется сразу»,
# specs/bp1/rpa-network-controls/spec.md).
_BLOCKING_HTTP_STATUSES = (401, 403, 429)


def _is_informative_html(html: str) -> bool:
    """True, если HTML содержит реальные элементы данных (ссылки).

    Многие сайты (Lenta.ru, SPA-приложения) отдают по HTTP «пустой скелет»
    (JS-shell): тело длинное, но настоящий контент появляется только после
    выполнения JS. Такая страница НЕ информативна — при отсутствии в ней
    достаточного числа ссылок её не стоит считать успешным результатом для
    не-JS-стратегий.

    Args:
        html: Исходный HTML.

    Returns:
        True, если страница содержит ``MIN_LINK_COUNT_FOR_CONTENT`` и более
        ссылок (элементов данных), иначе False.
    """
    if not html or not html.strip():
        return False
    # Считаем только ссылки на реальные (не-пустые) страницы. Лёгкая проверка
    # через ``html.parser`` (без BeautifulSoup) для скорости.
    import re

    # Грубая, но быстрая оценка: число вхождений ``href=``/``<a `` в HTML.
    # Для страниц-списков (новости, вакансии) этого достаточно, чтобы
    # отличить пустой JS-shell от страницы с данными.
    link_count = len(re.findall(r'<a[\s>]', html, flags=re.IGNORECASE))
    return link_count >= MIN_LINK_COUNT_FOR_CONTENT


# Порядок стратегий при деградации.
_DEGRADATION_ORDER = (
    StrategyType.FAST,
    StrategyType.CRAWL4AI,
    StrategyType.BROWSER,
    StrategyType.WAYBACK,
    StrategyType.STEALTH,
    StrategyType.HITL,
)

# Таблица «классификация -> допустимое подмножество _DEGRADATION_ORDER»
# (Шаг 12 плана рефакторинга, REFACTORING_PLAN.md — N10). Раньше классификация
# влияла только на то, С КАКОЙ стратегии начинать (``start_with``) — сам
# перебор всё равно проходил через все 6 стратегий по кругу, включая
# заведомо бесполезные для уже подтверждённой защиты (например, CRAWL4AI не
# умеет обходить антибот — ни один запрос через него не решит челлендж).
# Первое подходящее правило побеждает; порядок стратегий внутри значения —
# тот же, что и в _DEGRADATION_ORDER (сама последовательность деградации не
# меняется, меняется только то, какие стратегии в принципе рассматриваются).
_ALLOWED_STRATEGIES_TABLE: tuple[
    tuple[Callable[[SourceClassification], bool], tuple[StrategyType, ...]],
    ...,
] = (
    # CAPTCHA: FAST/CRAWL4AI/BROWSER не решают челлендж — сразу тяжёлые.
    (
        lambda c: c.has_captcha,
        (StrategyType.STEALTH, StrategyType.WAYBACK, StrategyType.HITL),
    ),
    # Антибот без SPA: CRAWL4AI не создан для обхода антибот-защиты (нет
    # собственного stealth-слоя) — пропускаем его, остальное пробуем.
    (
        lambda c: c.has_antibot and not c.is_spa,
        (
            StrategyType.FAST,
            StrategyType.BROWSER,
            StrategyType.WAYBACK,
            StrategyType.STEALTH,
            StrategyType.HITL,
        ),
    ),
)


def _allowed_strategies(
    classification: SourceClassification | None,
) -> tuple[StrategyType, ...]:
    """Допустимое подмножество ``_DEGRADATION_ORDER`` для классификации.

    Возвращает полный ``_DEGRADATION_ORDER``, если классификация
    отсутствует или не подпадает ни под одно правило таблицы —
    деградация ведёт себя как раньше (пробует всё по порядку). WAYBACK и
    HITL никогда не исключаются ни одним правилом: это универсальные
    стратегии «последней надежды», не завязанные на конкретный механизм
    защиты.
    """
    if classification is not None:
        for predicate, allowed in _ALLOWED_STRATEGIES_TABLE:
            if predicate(classification):
                return allowed
    return _DEGRADATION_ORDER


# User-Agent по умолчанию для HTTP-стратегий.
_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0 Safari/537.36'
)


def _ssl_unverified_context():
    """Возвращает SSL-контекст без проверки сертификата.

    Гос. порталы и некоторые коммерческие сайты отдают самоподписанные /
    недоверенные сертификаты, из-за чего ``urllib.request`` бросает
    ``CERTIFICATE_VERIFY_FAILED`` и FAST-стратегия ложно падает. Контекст без
    верификации используется как fallback (аналогично ``ignore_https_errors``
    в браузерных стратегиях) — но не для любого домена, см.
    ``_is_trusted_self_signed_domain`` (Шаг 13 плана рефакторинга, N11).
    """
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _is_trusted_self_signed_domain(url: str) -> bool:
    """True, если домен URL — из списка известных доменов с
    самоподписанными/недоверенными TLS-сертификатами (Шаг 13, N11).

    Раньше ``_fetch_sync`` при ЛЮБОЙ ошибке (включая
    ``CERTIFICATE_VERIFY_FAILED``) молча повторял запрос без проверки
    сертификата — риск MITM для произвольного домена, а не только для
    заведомо доверенных гос.порталов, для которых этот фолбэк изначально
    и задумывался. Ограничиваем его ``KNOWN_REGISTRY_DOMAINS`` — тем же
    списком, что использует ``SourceClassifier`` для детекции
    ``SourceType.REGISTRY`` и ``SearchParamResolver`` для выбора ИНН как
    поискового параметра.
    """
    host = try_extract_host(url)
    return host is not None and any(
        domain in host for domain in KNOWN_REGISTRY_DOMAINS
    )


def _fetch_sync(url: str, timeout_ms: int, user_agent: str) -> str:
    """Выполняет синхронный HTTP-запрос и возвращает тело ответа."""
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={'User-Agent': user_agent},
    )
    timeout = timeout_ms / 1000
    try:
        # Сначала обычный запрос с проверкой сертификата.
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception:
        if not _is_trusted_self_signed_domain(url):
            # Домен вне списка известных гос.порталов — TLS-ошибка
            # (или любая другая) остаётся ошибкой. FastStrategy падает,
            # деградация переходит дальше (BROWSER/STEALTH), где
            # ``ignore_https_errors=True`` уже осознанно применяется на
            # уровне контекста браузера, а не глобального SSL-контекста
            # Python.
            raise
        # Известный гос.портал с самоподписанным/недоверенным
        # сертификатом — повторяем без верификации, чтобы не ронять
        # FAST-стратегию на нём.
        with urllib.request.urlopen(
            req, timeout=timeout, context=_ssl_unverified_context()
        ) as resp:
            return resp.read().decode('utf-8', errors='replace')


class BaseStrategy(ABC):
    """Абстрактная стратегия обхода."""

    strategy_type: StrategyType

    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        """Выполняет запрос и возвращает результат."""
        raise NotImplementedError


class FastStrategy(BaseStrategy):
    """Быстрая стратегия — прямой HTTP-запрос (стандартная библиотека)."""

    strategy_type = StrategyType.FAST

    def __init__(self, timeout_ms: int = 30000):
        self._timeout_ms = timeout_ms

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        try:
            html = await asyncio.to_thread(
                _fetch_sync, url, self._timeout_ms, _DEFAULT_USER_AGENT
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=len(html) >= MIN_CONTENT_LENGTH,
                data=html,
                content_length=len(html),
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )


class WaybackStrategy(BaseStrategy):
    """Стратегия через Internet Archive Wayback Machine."""

    strategy_type = StrategyType.WAYBACK

    def __init__(self, timeout_ms: int = 30000):
        self._timeout_ms = timeout_ms

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        try:
            # 1. Получаем ближайший снапшот из API Wayback Machine.
            api_url = f'https://archive.org/wayback/available?url={url}'
            api_json = await asyncio.to_thread(
                _fetch_sync, api_url, self._timeout_ms, _DEFAULT_USER_AGENT
            )
            snapshot_url = self._extract_snapshot_url(api_json)
            if not snapshot_url:
                return StrategyResult(
                    strategy=self.strategy_type,
                    success=False,
                    error='no wayback snapshot available',
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

            # 2. Скачиваем сам HTML снапшота.
            html = await asyncio.to_thread(
                _fetch_sync,
                snapshot_url,
                self._timeout_ms,
                _DEFAULT_USER_AGENT,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=len(html) >= MIN_CONTENT_LENGTH,
                data=html,
                content_length=len(html),
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )

    @staticmethod
    def _extract_snapshot_url(api_json: str) -> str | None:
        """Извлекает URL снапшота из ответа API Wayback Machine."""
        import json

        try:
            data = json.loads(api_json)
            return (
                data.get('archived_snapshots', {}).get('closest', {}).get('url')
            )
        except (json.JSONDecodeError, AttributeError):
            return None


class BrowserStrategy(BaseStrategy):
    """Стратегия через Playwright (браузерная автоматизация)."""

    strategy_type = StrategyType.BROWSER

    def __init__(self, headless: bool = True, timeout_ms: int = 60000):
        self._headless = headless
        self._timeout_ms = timeout_ms

    # Количество попыток ожидания реального контента после goto. Многие сайты
    # (Lenta.ru, SPA) грузят результаты поиска асинхронно после события load,
    # поэтому контент из ``page.content()`` сразу после ``goto`` — пустой
    # JS-shell (нет ссылок/элементов данных).
    _CONTENT_POLL_ATTEMPTS = 10
    # Интервал (в секундах) между попытками проверки появления контента.
    _CONTENT_POLL_INTERVAL_S = 0.8

    # Селекторы, по которым опрашиваем появление реальных элементов данных.
    # Здесь же ведётся подсчёт ссылок на материалы, чтобы отличить страницу
    # с выдачей от навигационной оболочки (шапка/подвал).
    _NEWS_CONTAINER_SELECTORS = (
        'ul.search-results__list li',
        'ul.search-results__list.js-search-results-list li',
        'div[class*=search-results] li',
        '[class*=search-results] article',
        '[class*=search-result] li',
    )

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        p = None
        browser = None
        status: int | None = None
        try:
            from playwright.async_api import async_playwright

            p = await async_playwright().start()
            launch_kwargs: dict[str, Any] = {'headless': self._headless}
            proxy = kwargs.get('proxy')
            if proxy:
                launch_kwargs['proxy'] = {'server': proxy}
            browser = await p.chromium.launch(**launch_kwargs)
            # Игнорируем невалидные TLS-сертификаты (гос. порталы и др.
            # с самоподписанными/недоверенными сертификатами).
            context_kwargs: dict[str, Any] = {'ignore_https_errors': True}
            user_agent = kwargs.get('user_agent')
            if user_agent:
                context_kwargs['user_agent'] = user_agent
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()
            try:
                response = await page.goto(url, timeout=self._timeout_ms)
                status = response.status if response else None
            except Exception:
                # Если goto бросил исключение (таймаут/навигация), пробуем
                # всё равно прочитать текущий контент страницы ниже.
                pass

            # Дожидаемся появления реального контента (элементов данных).
            # Результаты поиска на SPA-сайтах и новостных порталах грузятся
            # асинхронно после события load (XHR/fetch), поэтому ``goto``
            # возвращается раньше, чем в DOM появятся результаты.
            #
            # ``wait_for_listing=False`` (передаётся из
            # ``AdaptiveParser._extract_article_text``) пропускает ожидание
            # контейнера результатов поиска: у ОТДЕЛЬНОЙ статьи такой
            # разметки никогда не будет, поэтому раньше здесь впустую ждали
            # до ``5 * 8с = 40с`` на каждой статье, не помещаясь в общий
            # бюджет `ARTICLE_FETCH_TIMEOUT_SECONDS` (20с, `core/config.py`).
            # Для статей достаточно общего опроса «появились ли вообще
            # ссылки» (``_wait_for_any_links``).
            found = False
            if kwargs.get('wait_for_listing', True):
                found = await self._wait_for_results_container(page)
            if not found:
                await self._wait_for_any_links(page)

            # Всегда читаем финальный контент после ожидания.
            try:
                html = await page.content()
            except Exception:
                html = ''

            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=len(html) >= MIN_CONTENT_LENGTH,
                data=html,
                content_length=len(html),
                elapsed_ms=elapsed,
                http_status=status,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
                http_status=status,
            )
        finally:
            await self._cleanup(p, browser)

    async def _wait_for_results_container(self, page) -> bool:
        """Ждёт появления контейнера результатов поиска по известным
        селекторам (``page.wait_for_selector``: ждёт именно появления
        элемента в DOM, не зависает на постоянных соединениях в отличие
        от networkidle, и корректно обрабатывает навигацию/перестройку
        DOM). Возвращает ``True``, если контейнер появился хотя бы по
        одному из селекторов.
        """
        for selector in self._NEWS_CONTAINER_SELECTORS:
            try:
                await page.wait_for_selector(
                    selector,
                    timeout=min(
                        self._CONTENT_POLL_ATTEMPTS
                        * int(self._CONTENT_POLL_INTERVAL_S * 1000),
                        self._timeout_ms,
                    ),
                )
                return True
            except Exception:
                continue
        return False

    async def _wait_for_any_links(self, page) -> None:
        """Опрашивает страницу, пока в ней не появятся хоть какие-то
        ссылки (см. ``_is_informative_html``), либо не истощится бюджет
        попыток.
        """
        for _ in range(self._CONTENT_POLL_ATTEMPTS):
            try:
                html = await page.content()
            except Exception:
                html = ''
            if _is_informative_html(html):
                return
            await asyncio.sleep(self._CONTENT_POLL_INTERVAL_S)

    @staticmethod
    async def _cleanup(p, browser) -> None:
        """Гарантированно освобождает ресурсы Playwright даже при отмене
        корутины (asyncio.wait_for / fetch_with_timeout). ``shield``
        защищает close()/stop() от отмены, чтобы процесс не завис.
        """
        if browser is not None:
            try:
                await asyncio.shield(browser.close())
            except Exception:
                pass
        if p is not None:
            try:
                await asyncio.shield(p.stop())
            except Exception:
                pass


class AgenticOrchestrator:
    """
    Оркестратор стратегий обхода с автоматической деградацией.

    Иерархия: FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL.

    Использует реальные движки (crawl4ai, stealth, HITL) вместо заглушек.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 60000,
        profiles_dir: str = './src/bp1/data/profiles',
        logger: logging.Logger | None = None,
    ):
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._logger = logger or logging.getLogger(__name__)
        self._strategies: dict[StrategyType, BaseStrategy] = {}
        self._register_strategies(profiles_dir=profiles_dir)
        # Прокси для RPA-стратегий (ТЗ BP-1) — без привязанного Redis
        # работает без кэша пула/cooldown, но не падает (bind_redis()).
        self._proxy_pool = ProxyPool()

    def bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к пулу прокси (кэш пула, cooldown)."""
        if self._proxy_pool.redis is None:
            self._proxy_pool.redis = redis_client

    def _register_strategies(self, profiles_dir: str) -> None:
        """Регистрирует реальные стратегии обхода."""
        from .engines import build_default_strategies

        self._strategies = build_default_strategies(
            headless=self._headless,
            timeout_ms=self._timeout_ms,
            profiles_dir=profiles_dir,
            logger=self._logger,
        )

    def register_strategy(
        self, strategy_type: StrategyType, strategy: BaseStrategy
    ) -> None:
        """Регистрирует пользовательскую стратегию."""
        self._strategies[strategy_type] = strategy

    async def fetch_with_degradation(
        self,
        url: str,
        start_with: StrategyType | None = None,
        classification: SourceClassification | None = None,
        **kwargs,
    ) -> StrategyResult:
        """
        Выполняет запрос с автоматической деградацией.

        1. Пробует FAST (прямой HTTP-запрос)
        2. Если контент короче 300 символов → CRAWL4AI
        3. Если CRAWL4AI не сработал → BROWSER (Playwright)
        4. Если BROWSER не сработал → WAYBACK (Internet Archive)
        5. Если все стратегии не сработали → HITL (человек)

        ``classification`` (Шаг 12 плана рефакторинга, N10) сужает перебор
        до подмножества ``_allowed_strategies()`` — заведомо бесполезные
        для уже подтверждённой защиты стратегии (например, CRAWL4AI при
        известном антиботе) не пробуются вовсе, а не просто откладываются
        на потом. При ``classification=None`` (или когда классификация не
        подпадает ни под одно правило таблицы) поведение не меняется —
        используется полный ``_DEGRADATION_ORDER``, как раньше.
        """
        base_order = _allowed_strategies(classification)

        start_index = 0
        if start_with is not None:
            try:
                start_index = base_order.index(start_with)
            except ValueError:
                start_index = 0
            # start_with задаёт лишь начало перебора: проходим от start_with
            # до конца цепочки, а затем «догоняем» стратегии из начала,
            # не повторяя уже пройденные. Так при провале STEALTH будут
            # испробованы HITL и остальные допустимые стратегии, а не
            # только STEALTH → HITL.
            trailing = base_order[start_index:]
            leading = tuple(
                t for t in base_order[:start_index] if t not in trailing
            )
            # Оба слагаемых — tuple, чтобы не получить
            # "can only concatenate tuple (not 'list') to tuple".
            order = trailing + leading
        else:
            order = base_order

        for strategy_type in order:
            strategy = self._strategies.get(strategy_type)
            if strategy is None:
                continue

            # kwargs для КОНКРЕТНОЙ попытки — не переиспользуется между
            # итерациями, чтобы прокси/UA, подобранные для RPA-стратегии,
            # не «утекали» в следующую (не-RPA) попытку в той же цепочке.
            call_kwargs = dict(kwargs)
            proxy_used: str | None = None
            if strategy_type in _RPA_STRATEGIES:
                proxy_used = await self._proxy_pool.acquire(url)
                if proxy_used is not None:
                    call_kwargs['proxy'] = proxy_used
                call_kwargs.setdefault('user_agent', get_random_user_agent())
                host = try_extract_host(url) or url
                await default_throttle.wait(host)

            self._logger.info(
                'Попытка стратегии %s для %s (прокси=%s)',
                strategy_type.value,
                url,
                proxy_used or 'нет',
            )
            result = await strategy.fetch(url, **call_kwargs)

            if (
                proxy_used is not None
                and result.http_status in _BLOCKING_HTTP_STATUSES
            ):
                self._logger.warning(
                    'Прокси %s заблокирован источником %s (HTTP %s) — cooldown',
                    proxy_used,
                    url,
                    result.http_status,
                )
                await self._proxy_pool.mark_blocked(url, proxy_used)

            # Проверка «информативности» контента: страница должна быть не
            # только достаточно длинной, но и содержать реальные элементы
            # данных (ссылки). Многие сайты отдают по HTTP пустой JS-shell
            # (Lenta.ru, SPA): длина больше MIN_CONTENT_LENGTH, но реального
            # контента нет, и парсер соберёт только пустой элемент. Для
            # не-JS-стратегий (FAST/CRAWL4AI) при таком контенте считаем
            # стратегию неуспешной и деградируем к JS-рендерингу
            # (BROWSER/STEALTH). Браузерные стратегии уже выполнили JS и
            # оцениваются только по длине.
            if (
                strategy_type not in _JS_RENDERING_STRATEGIES
                and result.success
                and result.data
                and not _is_informative_html(result.data)
            ):
                self._logger.warning(
                    'Стратегия %s для %s вернула неинформативный '
                    'контент (JS-shell, длина=%d) — деградация',
                    strategy_type.value,
                    url,
                    result.content_length,
                )
                result = StrategyResult(
                    strategy=strategy_type,
                    success=False,
                    data=result.data,
                    content_length=result.content_length,
                    error=(
                        'non-informative content (likely JS-shell, '
                        'no data elements)'
                    ),
                    elapsed_ms=result.elapsed_ms,
                )

            if result.success:
                self._logger.info(
                    'Стратегия %s успешна для %s (контент=%d, '
                    'длительность=%d мс)',
                    strategy_type.value,
                    url,
                    result.content_length,
                    result.elapsed_ms,
                )
                return result

            self._logger.warning(
                'Стратегия %s не сработала для %s: %s',
                strategy_type.value,
                url,
                result.error,
            )

        # Все стратегии не сработали.
        return StrategyResult(
            strategy=StrategyType.HITL,
            success=False,
            error='all strategies failed',
        )

    async def fetch_with_timeout(
        self,
        url: str,
        timeout_ms: int = 30000,
        cleanup_timeout_s: float = 5.0,
        **kwargs,
    ) -> StrategyResult:
        """
        Выполняет запрос с глобальным таймаутом.

        В отличие от ``asyncio.wait_for``, при срабатывании таймаута задача
        отменяется и ожидается её полное завершение, чтобы стратегии успели
        корректно освободить ресурсы (закрыть браузер, потоки и т.п.).
        """
        task = asyncio.ensure_future(self.fetch_with_degradation(url, **kwargs))
        try:
            done, _ = await asyncio.wait({task}, timeout=timeout_ms / 1000)
            if task in done:
                return task.result()
        except asyncio.CancelledError:
            task.cancel()
            raise

        # Таймаут: отменяем задачу и ждём завершения cleanup.
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=cleanup_timeout_s)
        except (asyncio.CancelledError, TimeoutError, Exception):
            pass

        return StrategyResult(
            strategy=StrategyType.FAST,
            success=False,
            error=f'timeout after {timeout_ms}ms',
        )
