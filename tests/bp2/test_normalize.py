from types import SimpleNamespace

from core.enums import NormStatus, RejectReason
from src.bp2.pipeline import (
    build_competitor_map,
    build_region_map,
    normalize_item,
)
from src.bp2.schemas import TITLE_PLACEHOLDER, RawEventIn


def _competitor(id_, name):
    return SimpleNamespace(id=id_, name=name, is_active=True)


def _region(id_, aliases):
    return SimpleNamespace(id=id_, name_aliases=aliases)


def _event(**kwargs):
    defaults = {
        'title': 'Тест',
        'url': 'https://example.com',
        'search_task_id': 1,
    }
    defaults.update(kwargs)
    return RawEventIn.model_validate(defaults)


COMP_MAP = {'бегемот': 1, 'топ-сервис': 2}
REGION_MAP = {'москва': 10, 'санкт-петербург': 11}
SOURCE_MAP = {1: 100}


# --- build_competitor_map ---


def test_build_competitor_map_lowercases():
    comps = [_competitor(1, 'Бегемот'), _competitor(2, 'Топ-Сервис')]
    result = build_competitor_map(comps)
    assert result == {'бегемот': 1, 'топ-сервис': 2}


# --- build_region_map ---


def test_build_region_map_expands_aliases():
    regions = [_region(10, ['москва', 'г. москва', 'г москва'])]
    result = build_region_map(regions)
    assert result['москва'] == 10
    assert result['г. москва'] == 10
    assert result['г москва'] == 10


def test_build_region_map_no_aliases():
    regions = [_region(10, None)]
    result = build_region_map(regions)
    assert result == {}


# --- normalize_item ---


def test_competitor_name_resolved_to_id():
    ev = _event(competitor='Бегемот', region='Москва', search_task_id=1)
    row = normalize_item(
        ev,
        raw_item_id=5,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['competitor_id'] == 1


def test_region_name_resolved_to_id():
    ev = _event(competitor='Бегемот', region='Москва', search_task_id=1)
    row = normalize_item(
        ev,
        raw_item_id=5,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['region_id'] == 10


def test_source_id_resolved_from_search_task():
    ev = _event(search_task_id=1)
    row = normalize_item(
        ev,
        raw_item_id=5,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['source_id'] == 100


def test_unknown_competitor_gives_none():
    ev = _event(competitor='Неизвестный')
    row = normalize_item(
        ev,
        raw_item_id=5,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['competitor_id'] is None


def test_title_placeholder_sets_rejected():
    ev = _event(title=TITLE_PLACEHOLDER)
    row = normalize_item(
        ev,
        raw_item_id=5,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['status'] == NormStatus.rejected
    assert row['reject_reason'] == RejectReason.parse_error


def test_normal_event_is_ok():
    ev = _event(title='Открытие склада')
    row = normalize_item(
        ev,
        raw_item_id=5,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['status'] == NormStatus.ok
    assert row['reject_reason'] is None


def test_dedup_key_is_set():
    ev = _event(title='Открытие склада', competitor='Бегемот')
    row = normalize_item(
        ev,
        raw_item_id=5,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['dedup_key'] and len(row['dedup_key']) == 64


def test_raw_item_id_preserved():
    ev = _event()
    row = normalize_item(
        ev,
        raw_item_id=99,
        competitor_map=COMP_MAP,
        region_map=REGION_MAP,
        source_map=SOURCE_MAP,
    )
    assert row['raw_item_id'] == 99
