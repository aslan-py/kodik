"""Тесты для реальных движков стратегий (engines.py)."""

import sys
from types import ModuleType

import pytest

from src.bp1.adaptive.schemas import StrategyType
from src.bp1.adaptive.strategies.engines import (
    Crawl4AIStrategy,
    HITLStrategy,
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
        StrategyType.HITL,
    ):
        assert strategy_type in strategies
        assert strategies[strategy_type].strategy_type == strategy_type
