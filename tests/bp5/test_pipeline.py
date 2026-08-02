"""Юнит-тесты детектора, сборки alert и текста письма — без БД.

detect_event_type, build_alert_rows и build_email_content — чистые функции:
заглушки (SimpleNamespace) вместо реальных моделей, только нужные поля.
"""

from datetime import date
from types import SimpleNamespace

from core.enums import AlertStatus, DeliveryMode, PriorityLevel
from src.bp5.pipeline import (
    build_alert_rows,
    build_email_content,
    build_telegram_content,
    detect_event_type,
)


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
    )
    assert len(rows) == 2
    assert {r['user_id'] for r in rows} == {10, 11}


def test_instant_stays_queued_after_build():
    """Исход доставки (sent/failed) решается позже, попыткой отправки —
    build_alert_rows больше не угадывает его по mode."""
    rows = build_alert_rows(
        make_event(),
        matched_type_id=1,
        rules=[rule(10, 1, DeliveryMode.instant)],
    )
    assert rows[0]['status'] == AlertStatus.queued
    assert rows[0]['sent_at'] is None


def test_digest_stays_queued_without_timestamp():
    rows = build_alert_rows(
        make_event(),
        matched_type_id=1,
        rules=[rule(10, 1, DeliveryMode.digest)],
    )
    assert rows[0]['status'] == AlertStatus.queued
    assert rows[0]['sent_at'] is None


def test_priority_snapshotted_from_event_display_label():
    rows = build_alert_rows(
        make_event(priority='П2'),
        matched_type_id=1,
        rules=[rule(10, 1, DeliveryMode.instant)],
    )
    assert rows[0]['priority'] == PriorityLevel.p2


def test_no_rules_gives_empty_list():
    rows = build_alert_rows(make_event(), matched_type_id=1, rules=[])
    assert rows == []


def test_showcase_event_id_and_type_id_carried_over():
    rows = build_alert_rows(
        make_event(),
        matched_type_id=7,
        rules=[rule(10, 1, DeliveryMode.instant)],
    )
    assert rows[0]['showcase_event_id'] == 42
    assert rows[0]['event_type_id'] == 7


# --- build_email_content ---


def make_showcase_event(**overrides):
    fields = {
        'title': 'Прокуратура начала проверку',
        'priority': 'П1',
        'category': 'Судебный риск',
        'region': 'Калужская область',
        'macro_region': 'ЦФО',
        'competitor': 'ООО Ромашка',
        'action': 'Подготовить ответ юристов',
        'deadline': date(2026, 8, 1),
        'department': 'Юристы',
        'source_url': 'https://example.com/news/1',
        'published_at': date(2026, 7, 28),
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_email_subject_contains_priority_category_and_title():
    subject, _ = build_email_content(make_showcase_event())
    assert 'П1' in subject
    assert 'Судебный риск' in subject
    assert 'Прокуратура начала проверку' in subject


def test_email_body_contains_all_filled_fields():
    _, body = build_email_content(make_showcase_event())
    assert 'Калужская область' in body
    assert 'ЦФО' in body
    assert 'ООО Ромашка' in body
    assert 'Подготовить ответ юристов' in body
    assert '2026-08-01' in body
    assert 'Юристы' in body
    assert 'https://example.com/news/1' in body
    assert '2026-07-28' in body


def test_email_body_uses_placeholder_for_missing_optional_fields():
    _, body = build_email_content(
        make_showcase_event(
            region=None,
            macro_region=None,
            competitor=None,
            action=None,
            deadline=None,
            department=None,
            source_url=None,
            published_at=None,
        )
    )
    assert body.count('—') == 8


# --- build_telegram_content ---


def test_telegram_content_contains_subject_and_body():
    """build_telegram_content переиспользует build_email_content — текст
    telegram-сообщения должен содержать и тему, и тело письма."""
    event = make_showcase_event()
    subject, body = build_email_content(event)
    text = build_telegram_content(event)
    assert subject in text
    assert body in text


def test_telegram_content_uses_placeholder_for_missing_optional_fields():
    text = build_telegram_content(
        make_showcase_event(
            region=None,
            macro_region=None,
            competitor=None,
            action=None,
            deadline=None,
            department=None,
            source_url=None,
            published_at=None,
        )
    )
    # 8 плейсхолдеров пустых полей + 1 разделитель "приоритет — категория"
    # в теме письма (build_email_content), которая тоже входит в текст.
    assert text.count('—') == 9
