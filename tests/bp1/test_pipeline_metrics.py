"""Тесты наблюдаемости прогона BP-1 (Шаг 20 плана рефакторинга, T6).

Проверяют сводку ``_summarize`` и проверку целостности цепочки стратегий
``check_strategy_chain``:

- доля успешных задач (``success_rate``);
- разбивка по РЕАЛЬНО сработавшим стратегиям;
- разбивка по уровням ``DataQualityGate``;
- список источников, не прошедших контроль качества;
- обратная совместимость прежних счётчиков (saved/unchanged/error/skipped).
"""

from __future__ import annotations

from src.bp1.adaptive.integration.runner import check_strategy_chain
from src.bp1.pipeline import _summarize


def _result(status: str, **extra) -> dict:
    return {'status': status, **extra}


def test_summarize_keeps_legacy_counters():
    """Прежние счётчики считаются как раньше."""
    summary = _summarize(
        [
            _result('saved'),
            _result('saved'),
            _result('unchanged'),
            _result('error'),
            _result('skipped'),
            _result('source_unavailable'),
        ]
    )

    assert summary['tasks'] == 6
    assert summary['saved'] == 2
    assert summary['unchanged'] == 1
    assert summary['error'] == 1
    # 'skipped' и 'source_unavailable' — обе в общий "пропущено".
    assert summary['skipped'] == 2


def test_summarize_success_rate():
    """success_rate — доля задач, давших данные (saved + unchanged)."""
    summary = _summarize(
        [
            _result('saved'),
            _result('unchanged'),
            _result('error'),
            _result('skipped'),
        ]
    )
    assert summary['success_rate'] == 0.5


def test_summarize_success_rate_empty_run():
    """Пустой прогон не делит на ноль."""
    assert _summarize([])['success_rate'] == 0.0


def test_summarize_breaks_down_by_actual_strategy():
    """Разбивка по стратегиям считает реально сработавшие."""
    summary = _summarize(
        [
            _result('saved', strategy='FAST'),
            _result('saved', strategy='STEALTH'),
            _result('unchanged', strategy='FAST'),
            _result('error'),  # без стратегии — не учитывается
        ]
    )
    assert summary['by_strategy'] == {'FAST': 2, 'STEALTH': 1}


def test_summarize_quality_levels():
    """Уровни Quality Gate агрегируются по прошёл/не прошёл."""
    levels_ok = {
        'SCHEMA': {'passed': True, 'errors': 0, 'warnings': 0},
        'CONSISTENCY': {'passed': True, 'errors': 0, 'warnings': 0},
    }
    levels_bad = {
        'SCHEMA': {'passed': True, 'errors': 0, 'warnings': 0},
        'CONSISTENCY': {'passed': False, 'errors': 3, 'warnings': 0},
    }
    summary = _summarize(
        [
            _result('saved', quality_levels=levels_ok),
            _result('saved', quality_levels=levels_bad),
        ]
    )

    assert summary['quality_levels']['SCHEMA'] == {'passed': 2, 'failed': 0}
    assert summary['quality_levels']['CONSISTENCY'] == {
        'passed': 1,
        'failed': 1,
    }


def test_summarize_collects_low_quality_sources():
    """Источники с проваленным Quality Gate попадают в отдельный список."""
    summary = _summarize(
        [
            _result('saved', quality_status='ok', source='good.ru'),
            _result('saved', quality_status='low_quality', source='bad.ru'),
            # Дубликат источника не повторяется в списке.
            _result('saved', quality_status='low_quality', source='bad.ru'),
        ]
    )
    assert summary['low_quality_sources'] == ['bad.ru']


def test_check_strategy_chain_reports_availability():
    """Проверка цепочки сообщает доступность опциональных пакетов."""

    class _FakeOrchestrator:
        def __init__(self):
            self._strategies = {'FAST': object(), 'BROWSER': object()}

    chain = check_strategy_chain(_FakeOrchestrator())

    assert set(chain) == {'crawl4ai', 'playwright', 'registered_count'}
    assert isinstance(chain['crawl4ai'], bool)
    assert isinstance(chain['playwright'], bool)
    assert chain['registered_count'] == 2


def test_check_strategy_chain_handles_missing_strategies():
    """Оркестратор без зарегистрированных стратегий не ломает проверку."""

    class _Empty:
        pass

    chain = check_strategy_chain(_Empty())
    assert chain['registered_count'] == 0
