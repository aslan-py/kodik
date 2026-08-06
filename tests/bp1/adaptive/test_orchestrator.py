"""1Тесты для AgenticOrchestrator."""

import pytest

from src.bp1.adaptive.orchestrator import (
    AgenticOrchestrator,
    BaseStrategy,
    WaybackStrategy,
)
from src.bp1.adaptive.schemas import StrategyResult, StrategyType


class _FailingStrategy(BaseStrategy):
    """Стратегия, которая всегда падает."""

    strategy_type = StrategyType.FAST

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        return StrategyResult(
            strategy=self.strategy_type,
            success=False,
            error='boom',
        )


class _SuccessStrategy(BaseStrategy):
    """Стратегия, которая всегда успешна."""

    strategy_type = StrategyType.BROWSER

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        return StrategyResult(
            strategy=self.strategy_type,
            success=True,
            data='<html>content</html>',
            content_length=500,
        )


@pytest.mark.asyncio
async def test_success_strategy_returns_result():
    """Успешная стратегия возвращает результат."""
    orch = AgenticOrchestrator()
    orch.register_strategy(StrategyType.FAST, _SuccessStrategy())
    result = await orch.fetch_with_degradation('https://example.com')
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
    result = await orch.fetch_with_degradation('https://example.com')
    assert result.success is False
    assert result.strategy == StrategyType.HITL


def test_extract_snapshot_url():
    """_extract_snapshot_url извлекает URL снапшота из ответа API."""
    api_json = (
        '{"archived_snapshots": {"closest": '
        '{"url": "http://web.archive.org/web/2026/snapshot"}}}'
    )
    url = WaybackStrategy._extract_snapshot_url(api_json)
    assert url == 'http://web.archive.org/web/2026/snapshot'


def test_extract_snapshot_url_missing():
    """_extract_snapshot_url возвращает None при отсутствии снапшота."""
    assert WaybackStrategy._extract_snapshot_url('{}') is None
    assert WaybackStrategy._extract_snapshot_url('not json') is None
