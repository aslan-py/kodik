"""Юнит-тесты сборки строки витрины — без БД.

build_showcase_row — чистая функция: раскладывает кортеж выборки по колонкам
витрины. Кортеж собираем заглушками (SimpleNamespace), порядок полей — как
в select_pending_events.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from core.enums import PriorityLevel, TonalityLevel
from src.bp4.pipeline import build_showcase_row


def make_row(
    *,
    priority=PriorityLevel.p2,
    tonality=TonalityLevel.positive,
    category='PR-активность конкурента',
    department='PR',
    competitor='Бегемот',
    region='Калуга',
    macro_region='ЦФО',
    latitude=54.5138,
    longitude=36.2612,
):
    """Кортеж в порядке select_pending_events со значениями по умолчанию."""
    event = SimpleNamespace(
        id=1,
        priority=priority,
        tonality=tonality,
        media_index=Decimal('47.10'),
        action='подготовить ответный PR-кейс',
        deadline=date(2026, 7, 25),
        comment='федеральное СМИ',
    )
    item = SimpleNamespace(
        raw_item_id=7,
        published_at=date(2026, 7, 18),
        title='Бегемот выиграл тендер',
        media_name='Big-news.ru',
        url='https://big-news.ru/news/123',
    )
    return (
        event,
        item,
        category,
        department,
        competitor,
        region,
        macro_region,
        latitude,
        longitude,
    )


# --- подстановка подписей вместо кодов enum'а ---


def test_priority_replaced_with_display_label():
    row = build_showcase_row(make_row(priority=PriorityLevel.p1))
    assert row['priority'] == 'П1'


def test_tonality_replaced_with_display_label():
    row = build_showcase_row(make_row(tonality=TonalityLevel.negative))
    assert row['tonality'] == 'негативная'


# --- раскладка полей по колонкам витрины ---


def test_facts_taken_from_normalized_item():
    row = build_showcase_row(make_row())
    assert row['title'] == 'Бегемот выиграл тендер'
    assert row['published_at'] == date(2026, 7, 18)
    assert row['media'] == 'Big-news.ru'
    assert row['source_url'] == 'https://big-news.ru/news/123'


def test_meanings_taken_from_categorized_event():
    row = build_showcase_row(make_row())
    assert row['action'] == 'подготовить ответный PR-кейс'
    assert row['deadline'] == date(2026, 7, 25)
    assert row['media_index'] == Decimal('47.10')
    assert row['comment'] == 'федеральное СМИ'


def test_dictionary_names_replace_ids():
    row = build_showcase_row(make_row())
    assert row['category'] == 'PR-активность конкурента'
    assert row['department'] == 'PR'
    assert row['competitor'] == 'Бегемот'
    assert row['region'] == 'Калуга'
    assert row['macro_region'] == 'ЦФО'


def test_coordinates_go_to_showcase():
    """Координаты нужны BI для метки на карте — джойнить region нельзя."""
    row = build_showcase_row(make_row())
    assert row['latitude'] == 54.5138
    assert row['longitude'] == 36.2612


def test_raw_item_id_kept_for_drill_down():
    """Из строки витрины должен быть переход к исходнику (требование ТЗ)."""
    row = build_showcase_row(make_row())
    assert row['raw_item_id'] == 7


def test_upsert_key_is_categorized_event_id():
    row = build_showcase_row(make_row())
    assert row['categorized_event_id'] == 1


# --- пустые справочники не роняют сборку (LEFT JOIN отдаёт None) ---


def test_missing_dictionary_values_become_none():
    row = build_showcase_row(
        make_row(
            department=None,
            competitor=None,
            region=None,
            macro_region=None,
            latitude=None,
            longitude=None,
        )
    )
    assert row['department'] is None
    assert row['competitor'] is None
    assert row['region'] is None
    assert row['macro_region'] is None
    assert row['latitude'] is None
    assert row['longitude'] is None
