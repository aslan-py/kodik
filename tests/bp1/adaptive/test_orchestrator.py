"""1Тесты для AgenticOrchestrator."""

import ssl
import sys
import urllib.request
from types import ModuleType

import pytest

from src.bp1.adaptive.schemas import (
    SourceClassification,
    StrategyResult,
    StrategyType,
)
from src.bp1.adaptive.strategies.orchestrator import (
    _DEGRADATION_ORDER,
    AgenticOrchestrator,
    BaseStrategy,
    BrowserStrategy,
    WaybackStrategy,
    _allowed_strategies,
    _fetch_sync,
    _is_trusted_self_signed_domain,
)

from .constants import (
    EXAMPLE_URL,
    MODULE_PLAYWRIGHT,
    ORCH_CONTENT,
    ORCH_CONTENT_LENGTH,
    ORCH_ERROR,
    SNAPSHOT_API_JSON,
    SNAPSHOT_URL,
)


class _FailingStrategy(BaseStrategy):
    """Стратегия, которая всегда падает."""

    strategy_type = StrategyType.FAST

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        return StrategyResult(
            strategy=self.strategy_type,
            success=False,
            error=ORCH_ERROR,
        )


class _SuccessStrategy(BaseStrategy):
    """Стратегия, которая всегда успешна."""

    strategy_type = StrategyType.BROWSER

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        return StrategyResult(
            strategy=self.strategy_type,
            success=True,
            data=ORCH_CONTENT,
            content_length=ORCH_CONTENT_LENGTH,
        )


@pytest.mark.asyncio
async def test_success_strategy_returns_result():
    """Успешная стратегия возвращает результат."""
    orch = AgenticOrchestrator()
    orch.register_strategy(StrategyType.FAST, _SuccessStrategy())
    result = await orch.fetch_with_degradation(EXAMPLE_URL)
    assert result.success is True
    assert result.strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_all_fail_returns_hitl():
    """Если все стратегии падают — возвращается HITL."""
    orch = AgenticOrchestrator()
    for strategy_type in (
        StrategyType.FAST,
        StrategyType.CRAWL4AI,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
        StrategyType.STEALTH,
        StrategyType.HITL,
    ):
        orch.register_strategy(strategy_type, _FailingStrategy())
    result = await orch.fetch_with_degradation(EXAMPLE_URL)
    assert result.success is False
    assert result.strategy == StrategyType.HITL


class _TrackingStrategy(BaseStrategy):
    """Стратегия, которая всегда падает и фиксирует порядок вызова."""

    def __init__(self, strategy_type: StrategyType, order: list):
        self.strategy_type = strategy_type
        self._order = order

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        self._order.append(self.strategy_type)
        return StrategyResult(
            strategy=self.strategy_type,
            success=False,
            error='tracked failure',
        )


@pytest.mark.asyncio
async def test_degradation_start_with_continues_full_chain():
    """При start_with перебор продолжается по всей иерархии.

    Раньше при start_with=STEALTH перебирались только STEALTH → HITL,
    из-за чего BROWSER/WAYBACK/FAST/CRAWL4AI пропускались. После правки
    start_with задаёт лишь начало, а при провале перебор проходит по
    полной цепочке (включая догонку стратегий из начала).
    """
    orch = AgenticOrchestrator()
    order: list = []
    for strategy_type in (
        StrategyType.FAST,
        StrategyType.CRAWL4AI,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
        StrategyType.STEALTH,
        StrategyType.HITL,
    ):
        orch.register_strategy(
            strategy_type, _TrackingStrategy(strategy_type, order)
        )

    result = await orch.fetch_with_degradation(
        EXAMPLE_URL, start_with=StrategyType.STEALTH
    )
    assert result.success is False
    # STEALTH первый (start_with), затем HITL, затем догонка начала:
    # FAST, CRAWL4AI, BROWSER, WAYBACK.
    assert order == [
        StrategyType.STEALTH,
        StrategyType.HITL,
        StrategyType.FAST,
        StrategyType.CRAWL4AI,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
    ]
    # HITL не дублируется в догонке.
    assert order.count(StrategyType.HITL) == 1


def test_extract_snapshot_url():
    """_extract_snapshot_url извлекает URL снапшота из ответа API."""
    url = WaybackStrategy._extract_snapshot_url(SNAPSHOT_API_JSON)
    assert url == SNAPSHOT_URL


def test_extract_snapshot_url_missing():
    """_extract_snapshot_url возвращает None при отсутствии снапшота."""
    assert WaybackStrategy._extract_snapshot_url('{}') is None
    assert WaybackStrategy._extract_snapshot_url('not json') is None


# ============================================================================
# Шаг 12: персонализация порядка деградации по классификации (N10)
# ============================================================================


def _classification(**overrides) -> SourceClassification:
    return SourceClassification(source_name='x', **overrides)


def test_allowed_strategies_no_classification_returns_full_order():
    """Без классификации — полный порядок деградации, как раньше."""
    assert _allowed_strategies(None) == _DEGRADATION_ORDER


def test_allowed_strategies_no_matching_rule_returns_full_order():
    """Классификация без антибота/CAPTCHA не подпадает ни под одно
    правило — исключений нет."""
    assert _allowed_strategies(_classification()) == _DEGRADATION_ORDER


def test_allowed_strategies_captcha_skips_light_strategies():
    """CAPTCHA: FAST/CRAWL4AI/BROWSER исключены — заведомо не решают
    челлендж."""
    allowed = _allowed_strategies(_classification(has_captcha=True))
    assert StrategyType.FAST not in allowed
    assert StrategyType.CRAWL4AI not in allowed
    assert StrategyType.BROWSER not in allowed
    assert StrategyType.STEALTH in allowed
    assert StrategyType.WAYBACK in allowed
    assert StrategyType.HITL in allowed


def test_allowed_strategies_antibot_without_spa_skips_crawl4ai():
    """Антибот без SPA: CRAWL4AI исключён (не обходит антибот), остальные
    стратегии остаются допустимыми."""
    allowed = _allowed_strategies(
        _classification(has_antibot=True, is_spa=False)
    )
    assert StrategyType.CRAWL4AI not in allowed
    assert StrategyType.FAST in allowed
    assert StrategyType.BROWSER in allowed
    assert StrategyType.WAYBACK in allowed
    assert StrategyType.STEALTH in allowed
    assert StrategyType.HITL in allowed


def test_allowed_strategies_antibot_with_spa_returns_full_order():
    """Антибот + SPA не подпадает под правило антибота (оно требует
    ``not is_spa``) и не подпадает под CAPTCHA — ни одно правило не
    сработало, полный порядок."""
    allowed = _allowed_strategies(
        _classification(has_antibot=True, is_spa=True)
    )
    assert allowed == _DEGRADATION_ORDER


@pytest.mark.asyncio
async def test_fetch_with_degradation_antibot_skips_crawl4ai_in_practice():
    """Интеграционно: has_antibot=True (без SPA) — CRAWL4AI не пробуется
    вообще (а не просто откладывается на потом, как раньше)."""
    orch = AgenticOrchestrator()
    order: list = []
    for strategy_type in (
        StrategyType.FAST,
        StrategyType.CRAWL4AI,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
        StrategyType.STEALTH,
        StrategyType.HITL,
    ):
        orch.register_strategy(
            strategy_type, _TrackingStrategy(strategy_type, order)
        )

    result = await orch.fetch_with_degradation(
        EXAMPLE_URL,
        classification=_classification(has_antibot=True, is_spa=False),
    )
    assert result.success is False
    assert StrategyType.CRAWL4AI not in order
    assert order == [
        StrategyType.FAST,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
        StrategyType.STEALTH,
        StrategyType.HITL,
    ]


@pytest.mark.asyncio
async def test_fetch_with_degradation_captcha_skips_light_strategies():
    """Интеграционно: CAPTCHA — сразу тяжёлые стратегии, лёгкие не
    пробуются вовсе."""
    orch = AgenticOrchestrator()
    order: list = []
    for strategy_type in (
        StrategyType.FAST,
        StrategyType.CRAWL4AI,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
        StrategyType.STEALTH,
        StrategyType.HITL,
    ):
        orch.register_strategy(
            strategy_type, _TrackingStrategy(strategy_type, order)
        )

    result = await orch.fetch_with_degradation(
        EXAMPLE_URL, classification=_classification(has_captcha=True)
    )
    assert result.success is False
    assert order == [
        StrategyType.STEALTH,
        StrategyType.WAYBACK,
        StrategyType.HITL,
    ]


@pytest.mark.asyncio
async def test_fetch_with_degradation_start_with_excluded_falls_back():
    """start_with вне допустимого подмножества (например, устаревшая
    рекомендация CRAWL4AI при уже подтверждённом антиботе) не роняет
    вызов — перебор начинается с начала допустимого подмножества."""
    orch = AgenticOrchestrator()
    order: list = []
    for strategy_type in (
        StrategyType.FAST,
        StrategyType.CRAWL4AI,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
        StrategyType.STEALTH,
        StrategyType.HITL,
    ):
        orch.register_strategy(
            strategy_type, _TrackingStrategy(strategy_type, order)
        )

    result = await orch.fetch_with_degradation(
        EXAMPLE_URL,
        start_with=StrategyType.CRAWL4AI,  # исключён для этой классификации
        classification=_classification(has_antibot=True, is_spa=False),
    )
    assert result.success is False
    assert StrategyType.CRAWL4AI not in order
    assert order[0] == StrategyType.FAST


# ============================================================================
# Шаг 13: ограничение fallback без верификации TLS (N11)
# ============================================================================


def test_is_trusted_self_signed_domain():
    """Только известные гос.порталы считаются доверенными для fallback
    без верификации TLS."""
    assert _is_trusted_self_signed_domain('https://fedresurs.ru/x') is True
    assert _is_trusted_self_signed_domain('https://www.nalog.ru/y') is True
    assert _is_trusted_self_signed_domain('https://example.com') is False
    assert _is_trusted_self_signed_domain('not a url') is False


class _FakeResponse:
    """Фейковый ответ urlopen (контекстный менеджер с .read())."""

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def test_fetch_sync_untrusted_domain_ssl_error_propagates(monkeypatch):
    """TLS-ошибка на домене вне известных гос.порталов остаётся
    ошибкой — fallback без верификации не применяется (раньше применялся
    для любого домена)."""

    def _raise(*args, **kwargs):
        raise ssl.SSLCertVerificationError('certificate verify failed')

    monkeypatch.setattr(urllib.request, 'urlopen', _raise)

    with pytest.raises(ssl.SSLCertVerificationError):
        _fetch_sync('https://example.com', 5000, 'UA')


def test_fetch_sync_trusted_domain_retries_without_verification(monkeypatch):
    """TLS-ошибка на известном гос.портале — fallback без верификации
    по-прежнему срабатывает (поведение не изменилось для доверенного
    списка)."""
    calls: list[dict] = []

    def _urlopen(req, timeout=None, context=None):
        calls.append({'context': context})
        if context is None:
            raise ssl.SSLCertVerificationError('certificate verify failed')
        return _FakeResponse(b'ok content')

    monkeypatch.setattr(urllib.request, 'urlopen', _urlopen)

    result = _fetch_sync('https://fedresurs.ru/search', 5000, 'UA')
    assert result == 'ok content'
    assert len(calls) == 2
    assert calls[0]['context'] is None
    assert calls[1]['context'] is not None


# ============================================================================
# BrowserStrategy: wait_for_listing (регресс на "Future exception was never
# retrieved" / TargetClosedError при фетче отдельных статей)
# ============================================================================


class _FakePage:
    """Фейковая Playwright-страница: фиксирует вызовы wait_for_selector."""

    def __init__(self, html: str, matching_selectors: set[str] = frozenset()):
        self._html = html
        self._matching_selectors = matching_selectors
        self.wait_for_selector_calls: list[str] = []

    async def goto(self, url, timeout=None):
        return None

    async def wait_for_selector(self, selector, timeout=None):
        self.wait_for_selector_calls.append(selector)
        if selector not in self._matching_selectors:
            raise TimeoutError(f'no match for {selector}')

    async def content(self):
        return self._html


class _FakeContext:
    def __init__(self, page: _FakePage):
        self._page = page
        self.closed = False

    async def new_page(self):
        return self._page

    async def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, context: _FakeContext):
        self._context = context
        self.closed = False

    async def new_context(self, **kwargs):
        return self._context

    async def close(self):
        self.closed = True


class _FakePlaywrightManager:
    """Фейковый ``async_playwright()`` с полным рабочим циклом (без падений)."""

    def __init__(self, browser: _FakeBrowser):
        self._browser = browser
        self.stopped = False

    async def start(self):
        return self

    async def stop(self):
        self.stopped = True

    @property
    def chromium(self):
        return self

    async def launch(self, **kwargs):
        return self._browser


def _install_fake_working_playwright(monkeypatch, page: _FakePage):
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    fake = ModuleType(MODULE_PLAYWRIGHT)
    fake.async_playwright = lambda: _FakePlaywrightManager(browser)
    monkeypatch.setitem(sys.modules, MODULE_PLAYWRIGHT, fake)
    return browser, context


@pytest.mark.asyncio
async def test_browser_strategy_waits_for_listing_by_default(monkeypatch):
    """По умолчанию (страница результатов поиска) ждём разметку листинга."""
    html = '<html><body>' + ('x' * 400) + '</body></html>'
    page = _FakePage(html, matching_selectors={'ul.search-results__list li'})
    _install_fake_working_playwright(monkeypatch, page)

    strategy = BrowserStrategy()
    result = await strategy.fetch(EXAMPLE_URL)

    assert page.wait_for_selector_calls == ['ul.search-results__list li']
    assert result.success is True
    assert result.data == html


@pytest.mark.asyncio
async def test_browser_strategy_skips_listing_wait_for_articles(monkeypatch):
    """``wait_for_listing=False`` (отдельная статья) не ждёт разметку листинга.

    Регресс-тест: раньше ``BrowserStrategy`` всегда перебирала все 5
    селекторов листинга (до ``5 * 8с = 40с``) даже для фетча ОТДЕЛЬНОЙ
    статьи, где такой разметки в принципе не бывает — из-за чего внешний
    ``asyncio.wait_for(ARTICLE_FETCH_TIMEOUT_SECONDS=20с)``
    (``processing/parser.py::_deep_fetch``) регулярно отменял эту корутину
    прямо посреди ``page.wait_for_selector``, что и производило
    ``Future exception was never retrieved`` / ``TargetClosedError`` в
    логах (см. ``REFACTORING_PLAN.md``). При ``wait_for_listing=False``
    ``page.wait_for_selector`` не должен вызываться вовсе — используется
    только общий опрос «появились ли вообще ссылки» (``_is_informative_html``).
    """
    html = '<html><body>' + ('<a href="/x">x</a>' * 5) + '</body></html>'
    page = _FakePage(html, matching_selectors=set())
    _install_fake_working_playwright(monkeypatch, page)

    strategy = BrowserStrategy()
    result = await strategy.fetch(EXAMPLE_URL, wait_for_listing=False)

    assert page.wait_for_selector_calls == []
    assert result.data == html
