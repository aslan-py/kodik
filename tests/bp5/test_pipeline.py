"""Юнит-тесты детектора и сборки alert — без БД.

detect_event_type и build_alert_rows — чистые функции: заглушки
(SimpleNamespace) вместо реальных моделей, только нужные поля.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

from core.enums import AlertStatus, DeliveryMode, PriorityLevel
from src.bp5.pipeline import build_alert_rows, detect_event_type


def et(id_, keywords):
    return SimpleNamespace(id=id_, keywords=keywords)


# --- detect_event_type ---


def test_matches_by_keyword_in_title():
    types = [et(1, ['прокуратура', 'суд']), et(2, ['тендер'])]
    assert detect_event_type('Суд рассмотрел дело', types) == 1


def test_matches_case_insensitive():
    types = [et(1, ['прокуратура'])]
    assert detect_event_type('ПРОКУРАТУРА начала проверку', types) == 1


def test_no_match_returns_none():
    types = [et(1, ['прокуратура'])]
    assert detect_event_type('Конкурент открыл новый магазин', types) is None


def test_none_title_returns_none():
    types = [et(1, ['прокуратура'])]
    assert detect_event_type(None, types) is None


def test_empty_event_types_returns_none():
    assert detect_event_type('Прокуратура начала проверку', []) is None


def test_first_type_wins_on_multiple_matches():
    """Заголовок подходит под два типа — побеждает первый по порядку из БД."""
    types = [et(1, ['суд']), et(2, ['тендер'])]
    assert detect_event_type('Суд по итогам тендера', types) == 1


# --- build_alert_rows ---


def rule(user_id, channel_id, mode):
    return SimpleNamespace(user_id=user_id, channel_id=channel_id, mode=mode)


def make_event(priority='П1'):
    return SimpleNamespace(id=42, priority=priority)


def test_one_row_per_rule():
    rows = build_alert_rows(
        make_event(),
        matched_type_id=1,
        rules=[
            rule(10, 1, DeliveryMode.instant),
            rule(11, 2, DeliveryMode.digest),
        ],
        now=datetime.now(UTC),
    )
    assert len(rows) == 2
    assert {r['user_id'] for r in rows} == {10, 11}


def test_instant_marked_sent_with_timestamp():
    now = datetime.now(UTC)
    rows = build_alert_rows(
        make_event(),
        matched_type_id=1,
        rules=[rule(10, 1, DeliveryMode.instant)],
        now=now,
    )
    assert rows[0]['status'] == AlertStatus.sent
    assert rows[0]['sent_at'] == now


def test_digest_stays_queued_without_timestamp():
    rows = build_alert_rows(
        make_event(),
        matched_type_id=1,
        rules=[rule(10, 1, DeliveryMode.digest)],
        now=datetime.now(UTC),
    )
    assert rows[0]['status'] == AlertStatus.queued
    assert rows[0]['sent_at'] is None


def test_priority_snapshotted_from_event_display_label():
    rows = build_alert_rows(
        make_event(priority='П2'),
        matched_type_id=1,
        rules=[rule(10, 1, DeliveryMode.instant)],
        now=datetime.now(UTC),
    )
    assert rows[0]['priority'] == PriorityLevel.p2


def test_no_rules_gives_empty_list():
    rows = build_alert_rows(
        make_event(), matched_type_id=1, rules=[], now=datetime.now(UTC)
    )
    assert rows == []


def test_showcase_event_id_and_type_id_carried_over():
    rows = build_alert_rows(
        make_event(),
        matched_type_id=7,
        rules=[rule(10, 1, DeliveryMode.instant)],
        now=datetime.now(UTC),
    )
    assert rows[0]['showcase_event_id'] == 42
    assert rows[0]['event_type_id'] == 7
