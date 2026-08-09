"""1Тесты для AgenticOrchestrator."""

import pytest

from src.bp1.adaptive.schemas import StrategyResult, StrategyType
from src.bp1.adaptive.strategies.orchestrator import (
    AgenticOrchestrator,
    BaseStrategy,
    WaybackStrategy,
)

from .constants import (
    EXAMPLE_URL,
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
