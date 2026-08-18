"""Тесты для реальных движков стратегий (engines.py)."""

import sys
from types import ModuleType

import pytest

from src.bp1.adaptive.schemas import StrategyType
from src.bp1.adaptive.strategies.engines import (
    Crawl4AIStrategy,
    HITLStrategy,
    StealthSpaStrategy,
    StealthStrategy,
    build_default_strategies,
)

from .constants import (
    ENGINE_FAKE_ERROR,
    ENGINE_HITL_ERROR,
    ENGINE_HITL_REQUEST_ID,
    ENGINE_HITL_RESOLVED_CONTENT_REPEAT,
    ENGINE_HITL_SESSION_COOKIE,
    ENGINE_PLAYWRIGHT_ERROR,
    EXAMPLE_SOURCE_NAME,
    EXAMPLE_URL,
    MODULE_CRAWL4AI,
    MODULE_PLAYWRIGHT,
)


class _FakeCrawler:
    """Фейковый AsyncWebCrawler, который падает при запуске."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def arun(self, url, config):
        raise RuntimeError(ENGINE_FAKE_ERROR)


def _install_fake_crawl4ai(monkeypatch):
    """Подменить модуль crawl4ai фейком, падающим при запуске."""
    fake = ModuleType(MODULE_CRAWL4AI)
    fake.AsyncWebCrawler = lambda config: _FakeCrawler()
    fake.BrowserConfig = lambda **kw: None
    fake.CrawlerRunConfig = lambda **kw: None
    monkeypatch.setitem(sys.modules, MODULE_CRAWL4AI, fake)


class _FakeChromium:
    """Фейковый chromium, который падает при запуске браузера."""

    async def launch(self, **kwargs):
        raise RuntimeError(ENGINE_PLAYWRIGHT_ERROR)


class _FakePlaywright:
    """Фейковый async_playwright, возвращающий падающий chromium."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def chromium(self):
        return _FakeChromium()


def _install_fake_playwright(monkeypatch):
    """Подменить playwright.async_api фейком, падающим при запуске."""
    fake = ModuleType(MODULE_PLAYWRIGHT)
    fake.async_playwright = lambda: _FakePlaywright()
    monkeypatch.setitem(sys.modules, MODULE_PLAYWRIGHT, fake)


@pytest.mark.asyncio
async def test_crawl4ai_strategy_returns_failure_on_error(monkeypatch):
    """Crawl4AIStrategy возвращает failure при ошибке импорта/запуска."""
    _install_fake_crawl4ai(monkeypatch)
    strategy = Crawl4AIStrategy()
    result = await strategy.fetch(EXAMPLE_URL)
    assert result.success is False
    assert result.strategy == StrategyType.CRAWL4AI


@pytest.mark.asyncio
async def test_stealth_strategy_returns_failure_on_error(monkeypatch):
    """StealthStrategy возвращает failure при ошибке запуска браузера."""
    _install_fake_playwright(monkeypatch)
    strategy = StealthStrategy()
    result = await strategy.fetch(EXAMPLE_URL)
    assert result.success is False
    assert result.strategy == StrategyType.STEALTH


# ============================================================================
# StealthSpaStrategy: ожидание networkidle перед чтением содержимого
# (change wait-for-spa-render-before-capture)
# ============================================================================


class _StealthSpaFakeResponse:
    def __init__(self, status: int = 200):
        self.status = status


class _StealthSpaFakePage:
    """Фейковая Playwright-страница: несколько последовательных ответов

    ``content()`` (эмулирует дозагрузку контента после ``networkidle``).
    """

    def __init__(
        self,
        html_sequence: list[str],
        wait_for_load_state_error: Exception | None = None,
    ):
        self._html_sequence = list(html_sequence)
        self._wait_for_load_state_error = wait_for_load_state_error
        self.wait_for_load_state_calls: list[tuple] = []
        self.content_calls = 0

    async def goto(self, url, timeout=None):
        return _StealthSpaFakeResponse(status=200)

    async def wait_for_load_state(self, state, timeout=None):
        self.wait_for_load_state_calls.append((state, timeout))
        if self._wait_for_load_state_error is not None:
            raise self._wait_for_load_state_error

    async def content(self):
        self.content_calls += 1
        if len(self._html_sequence) > 1:
            return self._html_sequence.pop(0)
        return self._html_sequence[0]


class _StealthSpaFakeContext:
    def __init__(self, page: _StealthSpaFakePage):
        self._page = page
        self.closed = False

    async def new_page(self):
        return self._page

    async def close(self):
        self.closed = True


class _StealthSpaFakeBrowser:
    def __init__(self, context: _StealthSpaFakeContext):
        self._context = context
        self.closed = False

    async def new_context(self, **kwargs):
        return self._context

    async def close(self):
        self.closed = True


class _StealthSpaFakePlaywright:
    def __init__(self, browser: _StealthSpaFakeBrowser):
        self._browser = browser

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @property
    def chromium(self):
        return self

    async def launch(self, **kwargs):
        return self._browser


def _install_stealth_spa_playwright(monkeypatch, page: _StealthSpaFakePage):
    context = _StealthSpaFakeContext(page)
    browser = _StealthSpaFakeBrowser(context)
    fake = ModuleType(MODULE_PLAYWRIGHT)
    fake.async_playwright = lambda: _StealthSpaFakePlaywright(browser)
    monkeypatch.setitem(sys.modules, MODULE_PLAYWRIGHT, fake)
    return browser, context


def _install_fake_stealth_module(monkeypatch):
    """Подменяет ``src.bp1.collectors.stealth``: не читаем реальный

    JS-файл, не делаем реальных Playwright-вызовов внутри
    ``apply_stealth``/``bypass_qrator`` (у фейкового context/page нет
    ``add_init_script`` и т.п. — тестируем именно ожидание, а не сам
    stealth-слой, который уже используется и в ``StealthStrategy``).
    """
    import src.bp1.collectors.stealth as stealth_module

    async def _fake_apply_stealth(context, *a, **kw):
        return None

    async def _fake_bypass_qrator(*a, **kw):
        return True

    monkeypatch.setattr(stealth_module, 'apply_stealth', _fake_apply_stealth)
    monkeypatch.setattr(stealth_module, 'bypass_qrator', _fake_bypass_qrator)
    monkeypatch.setattr(stealth_module, 'get_context_config', lambda **kw: {})
    monkeypatch.setattr(stealth_module, 'get_launch_args', lambda **kw: [])


@pytest.mark.asyncio
async def test_stealth_spa_strategy_returns_failure_on_error(monkeypatch):
    """StealthSpaStrategy возвращает failure при ошибке запуска браузера

    (то же поведение, что у StealthStrategy — стратегия скопирована, не
    переписана с нуля).
    """
    _install_fake_playwright(monkeypatch)
    strategy = StealthSpaStrategy()
    result = await strategy.fetch(EXAMPLE_URL)
    assert result.success is False
    assert result.strategy == StrategyType.STEALTH_SPA


@pytest.mark.asyncio
async def test_stealth_spa_strategy_waits_for_networkidle(monkeypatch):
    """Дожидается networkidle перед чтением содержимого страницы."""
    _install_fake_stealth_module(monkeypatch)
    html = '<html><body>' + ('<a href="/x">x</a>' * 20) + '</body></html>'
    page = _StealthSpaFakePage([html])
    _install_stealth_spa_playwright(monkeypatch, page)

    strategy = StealthSpaStrategy()
    result = await strategy.fetch(EXAMPLE_URL)

    assert page.wait_for_load_state_calls == [
        ('networkidle', StealthSpaStrategy._NETWORKIDLE_TIMEOUT_MS)
    ]
    assert result.success is True
    assert result.data == html
    assert result.strategy == StrategyType.STEALTH_SPA


@pytest.mark.asyncio
async def test_stealth_spa_strategy_continues_after_networkidle_timeout(
    monkeypatch,
):
    """Таймаут ожидания networkidle не блокирует fetch — читаем то, что

    успело отрисоваться, вместо зависания.
    """
    _install_fake_stealth_module(monkeypatch)
    html = '<html><body>' + ('<a href="/x">x</a>' * 20) + '</body></html>'
    page = _StealthSpaFakePage(
        [html], wait_for_load_state_error=TimeoutError('no idle')
    )
    _install_stealth_spa_playwright(monkeypatch, page)

    strategy = StealthSpaStrategy()
    result = await strategy.fetch(EXAMPLE_URL)

    assert result.success is True
    assert result.data == html


@pytest.mark.asyncio
async def test_stealth_spa_strategy_polls_when_content_looks_like_shell(
    monkeypatch,
):
    """Первый ``content()`` — голая оболочка (почти без ссылок); после

    короткого опроса подхватывается реально дозагрузившийся контент.
    """
    _install_fake_stealth_module(monkeypatch)
    shell_html = '<html><body>shell, no links</body></html>'
    real_html = '<html><body>' + ('<a href="/x">x</a>' * 20) + '</body></html>'
    page = _StealthSpaFakePage([shell_html, real_html])
    _install_stealth_spa_playwright(monkeypatch, page)

    strategy = StealthSpaStrategy()
    result = await strategy.fetch(EXAMPLE_URL)

    assert result.data == real_html
    assert page.content_calls >= 2


@pytest.mark.asyncio
async def test_hitl_strategy_returns_failure_without_profile(
    tmp_path, monkeypatch
):
    """HITLStrategy возвращает failure, если требуется участие человека."""
    from src.bp1.adaptive.schemas import HITLResponse

    strategy = HITLStrategy(profiles_dir=str(tmp_path))

    async def _fake_handle_challenge(**kwargs):
        return HITLResponse(
            request_id=ENGINE_HITL_REQUEST_ID,
            success=False,
            error=ENGINE_HITL_ERROR,
        )

    monkeypatch.setattr(
        strategy._hitl, 'handle_challenge', _fake_handle_challenge
    )
    result = await strategy.fetch(EXAMPLE_URL, source_name=EXAMPLE_SOURCE_NAME)
    assert result.success is False
    assert result.strategy == StrategyType.HITL
    assert 'human' in (result.error or '')


@pytest.mark.asyncio
async def test_hitl_strategy_returns_html_on_success(tmp_path, monkeypatch):
    """HITLStrategy передаёт HTML и content_length после решения CAPTCHA."""
    from src.bp1.adaptive.schemas import HITLResponse

    strategy = HITLStrategy(profiles_dir=str(tmp_path))
    # Длина HTML должна быть >= MIN_CONTENT_LENGTH (300), чтобы стратегия
    # считалась успешной.
    html = (
        '<html><body>'
        + ('resolved content ' * ENGINE_HITL_RESOLVED_CONTENT_REPEAT)
        + '</body></html>'
    )

    async def _fake_handle_challenge(**kwargs):
        return HITLResponse(
            request_id=ENGINE_HITL_REQUEST_ID,
            success=True,
            cookies={'session': ENGINE_HITL_SESSION_COOKIE},
            html=html,
        )

    monkeypatch.setattr(
        strategy._hitl, 'handle_challenge', _fake_handle_challenge
    )
    result = await strategy.fetch(EXAMPLE_URL, source_name=EXAMPLE_SOURCE_NAME)
    assert result.success is True
    assert result.strategy == StrategyType.HITL
    assert result.data == html
    assert result.content_length == len(html)


def test_build_default_strategies_has_all_types():
    """build_default_strategies возвращает все стратегии иерархии."""
    strategies = build_default_strategies()
    for strategy_type in (
        StrategyType.FAST,
        StrategyType.CRAWL4AI,
        StrategyType.BROWSER,
        StrategyType.WAYBACK,
        StrategyType.STEALTH,
        StrategyType.STEALTH_SPA,
        StrategyType.HITL,
    ):
        assert strategy_type in strategies
        assert strategies[strategy_type].strategy_type == strategy_type
