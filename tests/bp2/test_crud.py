"""Интеграционные тесты BP-2 CRUD — требуют реальной БД.

Сессия из conftest не делает commit — данные откатываются после каждого теста.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from core.enums import NormStatus, RawItemStatus, RejectReason
from src.bp1.models import Competitor, RawItem, SearchTask, Source
from src.bp2.crud import Bp2Crud
from src.bp2.models import NormalizedItem

# ============================================================================
#  Вспомогательные фикстуры
# ============================================================================


@pytest.fixture
async def competitor(session):
    c = Competitor(name='__тест__', is_active=True)
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def source(session):
    s = Source(name='__тест-источник__', is_active=True)
    session.add(s)
    await session.flush()
    return s


@pytest.fixture
async def task(session, competitor, source):
    t = SearchTask(
        competitor_id=competitor.id, source_id=source.id, trigger_id=None
    )
    session.add(t)
    await session.flush()
    return t


def _raw(task_id, status=RawItemStatus.new, *, created_at=None, raw_data=None):
    now = created_at or datetime.now(UTC)
    return RawItem(
        search_task_id=task_id,
        status=status,
        content_hash=None,
        raw_data=raw_data or {'meta': {'search_task_id': task_id}, 'items': []},
        created_at=now,
        updated_at=now,
    )


def _norm_row(raw_item_id, dedup_key):
    return {
        'raw_item_id': raw_item_id,
        'title': 'Тест',
        'dedup_key': dedup_key,
        'status': NormStatus.ok,
    }


# ============================================================================
#  select_pending_raw_items
# ============================================================================


async def test_new_item_is_pending(session, task):
    raw = _raw(task.id)
    session.add(raw)
    await session.flush()

    crud = Bp2Crud(session)
    pending = await crud.select_pending_raw_items()
    ids = [r.id for r in pending]
    assert raw.id in ids


async def test_error_item_not_pending(session, task):
    raw = _raw(task.id, status=RawItemStatus.error)
    session.add(raw)
    await session.flush()

    crud = Bp2Crud(session)
    pending = await crud.select_pending_raw_items()
    ids = [r.id for r in pending]
    assert raw.id not in ids


async def test_changed_replaces_new(session, task):
    t1 = datetime(2026, 6, 20, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 6, 21, 10, 0, 0, tzinfo=UTC)
    old = _raw(task.id, RawItemStatus.new, created_at=t1)
    new = _raw(task.id, RawItemStatus.changed, created_at=t2)
    session.add_all([old, new])
    await session.flush()

    crud = Bp2Crud(session)
    pending = await crud.select_pending_raw_items()
    ids = [r.id for r in pending]
    assert new.id in ids
    assert old.id not in ids


async def test_already_normalized_not_pending(session, task):
    raw = _raw(task.id)
    session.add(raw)
    await session.flush()

    norm = NormalizedItem(
        raw_item_id=raw.id,
        title='Тест',
        dedup_key='xyz99',
        status=NormStatus.ok,
    )
    session.add(norm)
    await session.flush()

    crud = Bp2Crud(session)
    pending = await crud.select_pending_raw_items()
    ids = [r.id for r in pending]
    assert raw.id not in ids


async def test_tiebreak_by_id(session, task):
    """При одинаковом created_at побеждает снимок с большим id (changed)."""
    same_time = datetime(2026, 6, 23, 15, 0, 0, tzinfo=UTC)
    old = _raw(task.id, RawItemStatus.new, created_at=same_time)
    session.add(old)
    await session.flush()
    newer = _raw(task.id, RawItemStatus.changed, created_at=same_time)
    session.add(newer)
    await session.flush()

    crud = Bp2Crud(session)
    pending = await crud.select_pending_raw_items()
    ids = [r.id for r in pending]
    assert newer.id in ids
    assert old.id not in ids


# ============================================================================
#  select_reparse_raw_items
# ============================================================================


async def test_reparse_includes_already_normalized(session, task):
    """В отличие от select_pending_raw_items, уже нормализованный снимок

    для переразбора не исключается — правкам справочника нужно видеть
    и его тоже.
    """
    raw = _raw(task.id)
    session.add(raw)
    await session.flush()

    norm = NormalizedItem(
        raw_item_id=raw.id,
        title='Тест',
        dedup_key='reparse_key_001',
        status=NormStatus.ok,
    )
    session.add(norm)
    await session.flush()

    crud = Bp2Crud(session)
    reparse = await crud.select_reparse_raw_items()
    ids = [r.id for r in reparse]
    assert raw.id in ids


async def test_reparse_filters_by_raw_item_ids(session, task):
    """raw_item_ids сужает выборку до конкретных id (точечный переразбор)."""
    raw_a = _raw(task.id)
    raw_b = _raw(task.id)
    session.add_all([raw_a, raw_b])
    await session.flush()

    crud = Bp2Crud(session)
    reparse = await crud.select_reparse_raw_items([raw_a.id])
    ids = [r.id for r in reparse]
    assert ids == [raw_a.id]


async def test_reparse_excludes_error_status(session, task):
    """error-снимки (raw_data=NULL) не годятся для переразбора, как и для

    обычного отбора.
    """
    raw = _raw(task.id, status=RawItemStatus.error)
    session.add(raw)
    await session.flush()

    crud = Bp2Crud(session)
    reparse = await crud.select_reparse_raw_items()
    ids = [r.id for r in reparse]
    assert raw.id not in ids


# ============================================================================
#  upsert_normalized_items
# ============================================================================


async def test_upsert_inserts_row(session, task):
    raw = _raw(task.id)
    session.add(raw)
    await session.flush()

    crud = Bp2Crud(session)
    await crud.upsert_normalized_items([_norm_row(raw.id, 'key_unique_001')])
    await session.flush()

    result = await session.execute(
        select(NormalizedItem).where(
            NormalizedItem.dedup_key == 'key_unique_001'
        )
    )
    assert result.scalars().first() is not None


async def test_upsert_empty_list_no_error(session):
    crud = Bp2Crud(session)
    await crud.upsert_normalized_items([])


async def test_upsert_duplicate_dedup_key_ignored(session, task):
    raw = _raw(task.id)
    session.add(raw)
    await session.flush()

    crud = Bp2Crud(session)
    row = _norm_row(raw.id, 'key_dedup_001')
    await crud.upsert_normalized_items([row])
    await crud.upsert_normalized_items([row])  # повтор
    await session.flush()

    result = await session.execute(
        select(NormalizedItem).where(
            NormalizedItem.dedup_key == 'key_dedup_001'
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_upsert_update_true_updates_existing_row_in_place(session, task):
    """update=True (переразбор) правит status/reject_reason у существующей

    строки на месте — id не меняется, дубль не создаётся.
    """
    raw = _raw(task.id)
    session.add(raw)
    await session.flush()

    crud = Bp2Crud(session)
    row = _norm_row(raw.id, 'key_reparse_001')
    await crud.upsert_normalized_items([row])
    await session.flush()

    original = (
        await session.execute(
            select(NormalizedItem).where(
                NormalizedItem.dedup_key == 'key_reparse_001'
            )
        )
    ).scalar_one()
    original_id = original.id

    updated_row = dict(row)
    updated_row['status'] = NormStatus.rejected
    updated_row['reject_reason'] = RejectReason.stop_word
    await crud.upsert_normalized_items([updated_row], update=True)
    await session.flush()
    # ON CONFLICT DO UPDATE идёт мимо ORM unit-of-work: уже загруженный
    # объект original в identity map не узнает про изменение сам собой.
    session.expire_all()

    result = await session.execute(
        select(NormalizedItem).where(
            NormalizedItem.dedup_key == 'key_reparse_001'
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].id == original_id
    assert rows[0].status == NormStatus.rejected
    assert rows[0].reject_reason == RejectReason.stop_word
