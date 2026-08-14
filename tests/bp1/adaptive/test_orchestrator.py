"""1Тесты для AgenticOrchestrator."""

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
    WaybackStrategy,
    _allowed_strategies,
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
