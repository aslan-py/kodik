from core.enums import RejectReason
from src.bp2.pipeline import (
    REASONS_COUNTED_BEFORE_WRITE,
    count_rejected_by_reason,
    summarize_raw_items,
)


def _row(reason=None):
    return {'reject_reason': reason}


def test_multiple_reasons_counted():
    rows = [
        _row(RejectReason.black_domain),
        _row(RejectReason.black_domain),
        _row(RejectReason.stop_word),
        _row(RejectReason.stop_topic),
        _row(RejectReason.false_positive),
        _row(RejectReason.parse_error),
        _row(None),  # status=ok, в разбивку не попадает
    ]
    counts = count_rejected_by_reason(rows)
    assert counts == {
        'black_domain': 2,
        'stop_word': 1,
        'stop_topic': 1,
        'false_positive': 1,
        'parse_error': 1,
    }


def test_no_rejections_returns_zeros():
    rows = [_row(None), _row(None)]
    counts = count_rejected_by_reason(rows)
    assert counts == {
        'black_domain': 0,
        'stop_word': 0,
        'stop_topic': 0,
        'false_positive': 0,
        'parse_error': 0,
    }


def test_empty_rows_returns_zeros():
    assert count_rejected_by_reason([]) == {
        'black_domain': 0,
        'stop_word': 0,
        'stop_topic': 0,
        'false_positive': 0,
        'parse_error': 0,
    }


def test_noise_limit_excluded_from_breakdown():
    """noise_rejected — отдельный постфактум-проход поверх записанных строк
    (см. run_bp2, шаг 8), в rows он появиться не может. Разбивка по
    причинам его не учитывает — поля не пересекаются и не задваиваются.
    """
    assert RejectReason.noise_limit not in REASONS_COUNTED_BEFORE_WRITE
    assert 'noise_limit' not in count_rejected_by_reason([])


def test_raw_summary_distinguishes_empty_input_from_rejected_rows():
    """BP-2 сообщает пустой вход отдельно от причин фильтрации."""

    class _Raw:
        def __init__(self, raw_data):
            self.raw_data = raw_data

    summary = summarize_raw_items(
        [
            _Raw(
                {
                    'meta': {'empty_reason': 'no_extractable_items'},
                    'items': [],
                }
            ),
            _Raw({'meta': {}, 'items': [{'title': 'Материал'}]}),
        ]
    )

    assert summary == {
        'source_items': 1,
        'empty_raw_items': 1,
        'empty_by_reason': {'no_extractable_items': 1},
    }
