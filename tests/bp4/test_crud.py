"""Интеграционные тесты BP-4 CRUD — требуют реальной БД.

Сессия из conftest не делает commit — данные откатываются после каждого теста.
Каждый тест строит минимальную цепочку слоёв:
competitor → source → search_task → raw_item → normalized_item →
categorized_event, а затем гоняет отбор и запись витрины.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from core.enums import NormStatus, PriorityLevel, RawItemStatus, TonalityLevel
from src.bp1.models import Competitor, RawItem, SearchTask, Source
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp4.crud import Bp4Crud
from src.bp4.models import ShowcaseEvent
from src.bp4.pipeline import build_showcase_row, sync_showcase

# ============================================================================
#  Вспомогательные фикстуры — цепочка слоёв
# ============================================================================


@pytest.fixture
async def competitor(session):
    c = Competitor(name=f'__тест-конкурент-{uuid4().hex[:8]}__')
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def source(session):
    s = Source(name=f'__тест-источник-{uuid4().hex[:8]}__')
    session.add(s)
    await session.flush()
    return s


@pytest.fixture
async def raw_item(session, competitor, source):
    task = SearchTask(
        competitor_id=competitor.id, source_id=source.id, trigger_id=None
    )
    session.add(task)
    await session.flush()
    now = datetime.now(UTC)
    raw = RawItem(
        search_task_id=task.id,
        status=RawItemStatus.new,
        raw_data={'meta': {'search_task_id': task.id}, 'items': []},
        created_at=now,
        updated_at=now,
    )
    session.add(raw)
    await session.flush()
    return raw


@pytest.fixture
async def category(session):
    name = f'__тест-категория-{uuid4().hex[:8]}__'
    c = Category(name=name)
    session.add(c)
    await session.flush()
    return c


@pytest.fixture
async def department(session):
    d = Department(name=f'__тест-отдел-{uuid4().hex[:8]}__')
    session.add(d)
    await session.flush()
    return d


async def make_normalized(session, raw_item, competitor, *, status=None):
    """Строка фактов (silver) со свежим dedup_key."""
    item = NormalizedItem(
        raw_item_id=raw_item.id,
        competitor_id=competitor.id,
        region_id=None,
        source_id=None,
        published_at=date(2026, 6, 25),
        title='Тестовое событие BP-4',
        media_name='Тест-СМИ',
        media_domain='test.ru',
        url=f'https://test.ru/{uuid4().hex[:8]}',
        text='Тело события',
        dedup_key=uuid4().hex,
        status=status or NormStatus.ok,
    )
    session.add(item)
    await session.flush()
    return item


async def make_categorized(session, item, category, department, **kwargs):
    """Строка смыслов (gold) по событию."""
    event = CategorizedEvent(
        normalized_item_id=item.id,
        priority=kwargs.get('priority', PriorityLevel.p2),
        category_id=category.id,
        tonality=kwargs.get('tonality', TonalityLevel.neutral),
        action='Отработать событие',
        deadline=date(2026, 7, 2),
        department_id=department.id,
        comment='Тестовая разметка',
        llm_model='test-model',
        prompt_version='v0',
        categorized_at=kwargs.get('categorized_at', datetime.now(UTC)),
    )
    session.add(event)
    await session.flush()
    return event


@pytest.fixture
async def categorized(session, raw_item, competitor, category, department):
    item = await make_normalized(session, raw_item, competitor)
    return await make_categorized(session, item, category, department)


# ============================================================================
#  select_pending_events
# ============================================================================


async def test_new_event_is_pending(session, categorized):
    crud = Bp4Crud(session)
    pending = await crud.select_pending_events()
    assert categorized.id in [row[0].id for row in pending]


async def test_rejected_item_not_pending(
    session, raw_item, competitor, category, department
):
    """Антишум мог пометить событие rejected уже ПОСЛЕ разметки BP-3."""
    item = await make_normalized(
        session, raw_item, competitor, status=NormStatus.rejected
    )
    event = await make_categorized(session, item, category, department)

    crud = Bp4Crud(session)
    pending = await crud.select_pending_events()
    assert event.id not in [row[0].id for row in pending]


async def test_published_event_not_pending(session, categorized):
    """После записи в витрину событие из отбора уходит."""
    crud = Bp4Crud(session)
    rows = [build_showcase_row(r) for r in await crud.select_pending_events()]
    await crud.upsert_showcase_events(rows)
    await session.flush()

    pending = await crud.select_pending_events()
    assert categorized.id not in [row[0].id for row in pending]


async def test_recategorized_event_is_pending_again(session, categorized):
    """Переразметка BP-3 (categorized_at сдвинулся) возвращает событие."""
    crud = Bp4Crud(session)
    rows = [build_showcase_row(r) for r in await crud.select_pending_events()]
    await crud.upsert_showcase_events(rows)
    await session.flush()

    categorized.priority = PriorityLevel.p1
    categorized.categorized_at = datetime.now(UTC) + timedelta(minutes=5)
    await session.flush()

    pending = await crud.select_pending_events()
    assert categorized.id in [row[0].id for row in pending]


# ============================================================================
#  upsert_showcase_events
# ============================================================================


async def test_upsert_inserts_row(session, categorized):
    crud = Bp4Crud(session)
    rows = [build_showcase_row(r) for r in await crud.select_pending_events()]
    await crud.upsert_showcase_events(rows)
    await session.flush()

    showcase = await session.scalar(
        select(ShowcaseEvent).where(
            ShowcaseEvent.categorized_event_id == categorized.id
        )
    )
    assert showcase is not None
    assert showcase.priority == 'П2'
    assert showcase.title == 'Тестовое событие BP-4'


async def test_upsert_empty_list_returns_zero(session):
    crud = Bp4Crud(session)
    assert await crud.upsert_showcase_events([]) == 0


async def test_upsert_twice_creates_no_duplicate(session, categorized):
    crud = Bp4Crud(session)
    rows = [build_showcase_row(r) for r in await crud.select_pending_events()]
    await crud.upsert_showcase_events(rows)
    await crud.upsert_showcase_events(rows)
    await session.flush()

    found = await session.execute(
        select(ShowcaseEvent).where(
            ShowcaseEvent.categorized_event_id == categorized.id
        )
    )
    assert len(found.scalars().all()) == 1


async def test_upsert_updates_existing_row(session, categorized):
    """Переразметка перезаписывает строку витрины и двигает updated_at."""
    crud = Bp4Crud(session)
    rows = [build_showcase_row(r) for r in await crud.select_pending_events()]
    await crud.upsert_showcase_events(rows)
    await session.flush()

    showcase = await session.scalar(
        select(ShowcaseEvent).where(
            ShowcaseEvent.categorized_event_id == categorized.id
        )
    )
    first_updated_at = showcase.updated_at

    categorized.priority = PriorityLevel.p1
    categorized.categorized_at = datetime.now(UTC) + timedelta(minutes=5)
    await session.flush()

    rows = [build_showcase_row(r) for r in await crud.select_pending_events()]
    await crud.upsert_showcase_events(rows)
    await session.flush()
    await session.refresh(showcase)

    assert showcase.priority == 'П1'
    assert showcase.updated_at > first_updated_at


# ============================================================================
#  sync_showcase (оркестратор в чужой сессии)
# ============================================================================


async def test_sync_showcase_reports_and_writes(session, categorized):
    summary = await sync_showcase(session)
    await session.flush()

    assert summary['pending'] >= 1
    assert summary['upserted'] >= 1

    showcase = await session.scalar(
        select(ShowcaseEvent).where(
            ShowcaseEvent.categorized_event_id == categorized.id
        )
    )
    assert showcase is not None


async def test_sync_showcase_is_idempotent(session, categorized):
    """Второй прогон подряд ничего не отбирает — инкремент работает."""
    await sync_showcase(session)
    await session.flush()

    second = await sync_showcase(session)
    assert second['pending'] == 0
    assert second['upserted'] == 0
