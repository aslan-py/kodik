"""Тесты для реальных движков стратегий (engines.py)."""

import sys
from types import ModuleType

import pytest

from src.bp1.adaptive.engines import (
    Crawl4AIStrategy,
    HITLStrategy,
    StealthStrategy,
    build_default_strategies,
)
from src.bp1.adaptive.schemas import StrategyType


class _FakeCrawler:
    """Фейковый AsyncWebCrawler, который падает при запуске."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def arun(self, url, config):
        raise RuntimeError('crawl4ai unavailable')


def _install_fake_crawl4ai(monkeypatch):
    """Подменить модуль crawl4ai фейком, падающим при запуске."""
    fake = ModuleType('crawl4ai')
    fake.AsyncWebCrawler = lambda config: _FakeCrawler()
    fake.BrowserConfig = lambda **kw: None
    fake.CrawlerRunConfig = lambda **kw: None
    monkeypatch.setitem(sys.modules, 'crawl4ai', fake)


class _FakeChromium:
    """Фейковый chromium, который падает при запуске браузера."""

    async def launch(self, **kwargs):
        raise RuntimeError('playwright unavailable')


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
    fake = ModuleType('playwright.async_api')
    fake.async_playwright = lambda: _FakePlaywright()
    monkeypatch.setitem(sys.modules, 'playwright.async_api', fake)


@pytest.mark.asyncio
async def test_crawl4ai_strategy_returns_failure_on_error(monkeypatch):
    """Crawl4AIStrategy возвращает failure при ошибке импорта/запуска."""
    _install_fake_crawl4ai(monkeypatch)
    strategy = Crawl4AIStrategy()
    result = await strategy.fetch('https://example.com')
    assert result.success is False
    assert result.strategy == StrategyType.CRAWL4AI


@pytest.mark.asyncio
async def test_stealth_strategy_returns_failure_on_error(monkeypatch):
    """StealthStrategy возвращает failure при ошибке запуска браузера."""
    _install_fake_playwright(monkeypatch)
    strategy = StealthStrategy()
    result = await strategy.fetch('https://example.com')
    assert result.success is False
    assert result.strategy == StrategyType.STEALTH


@pytest.mark.asyncio
async def test_hitl_strategy_returns_failure_without_profile(tmp_path):
    """HITLStrategy возвращает failure, если требуется участие человека."""
    strategy = HITLStrategy(profiles_dir=str(tmp_path))
    result = await strategy.fetch(
        'https://example.com', source_name='example.com'
    )
    assert result.success is False
    assert result.strategy == StrategyType.HITL
    assert 'human' in (result.error or '')


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
