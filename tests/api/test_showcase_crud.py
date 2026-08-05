"""Тесты фильтров ShowcaseCRUD.list_all (api/crud/showcase.py).

Раньше этот CRUD вообще не был покрыт тестами — здесь только то, что
нужно для проверки новых фильтров (title/category/priority/region/
competitor/department/published_from/published_to), не полный ретроактивный
набор для остального (get/update уже покрыты end-to-end через
tests/api/test_action_items.py::make_showcase_event и ручную проверку).
"""

from datetime import UTC, date, datetime
from uuid import uuid4

from api.crud.showcase import ShowcaseCRUD
from core.enums import NormStatus, PriorityLevel, RawItemStatus, TonalityLevel
from src.bp1.models import Competitor, RawItem, SearchTask, Source
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp4.constants import PRIORITY_DISPLAY
from src.bp4.models import ShowcaseEvent


async def make_event(
    session,
    *,
    title,
    region=None,
    competitor_name=None,
    department_name=None,
    published_at=date(2026, 6, 25),
    priority=PriorityLevel.p1,
):
    competitor = Competitor(
        name=competitor_name or f'__тест-конкурент-{uuid4().hex[:8]}__'
    )
    source = Source(name=f'__тест-источник-{uuid4().hex[:8]}__')
    category = Category(name=f'__тест-категория-{uuid4().hex[:8]}__')
    session.add_all([competitor, source, category])
    await session.flush()

    department = None
    if department_name is not None:
        department = Department(name=department_name)
        session.add(department)
        await session.flush()

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

    item = NormalizedItem(
        raw_item_id=raw.id,
        competitor_id=competitor.id,
        region_id=None,
        source_id=None,
        published_at=published_at,
        title=title,
        dedup_key=uuid4().hex,
        status=NormStatus.ok,
    )
    session.add(item)
    await session.flush()

    ce = CategorizedEvent(
        normalized_item_id=item.id,
        priority=priority,
        category_id=category.id,
        tonality=TonalityLevel.neutral,
        department_id=department.id if department else None,
        llm_model='test',
        prompt_version='v0',
    )
    session.add(ce)
    await session.flush()

    sc = ShowcaseEvent(
        categorized_event_id=ce.id,
        raw_item_id=raw.id,
        title=title,
        published_at=published_at,
        priority=PRIORITY_DISPLAY[priority],
        category=category.name,
        tonality='нейтральная',
        region=region,
        competitor=competitor.name,
        department=department.name if department else None,
    )
    session.add(sc)
    await session.flush()
    return sc


class TestListAllFilters:
    async def test_filters_by_title_substring(self, session):
        marker = uuid4().hex[:8]
        event = await make_event(session, title=f'Штраф {marker} за нарушения')
        await make_event(session, title='Совсем другое событие')
        crud = ShowcaseCRUD(session)

        events = await crud.list_all(title=marker)

        assert {e.id for e in events} == {event.id}

    async def test_filters_by_category_exact(self, session):
        event = await make_event(session, title='A')
        await make_event(session, title='B')
        crud = ShowcaseCRUD(session)

        events = await crud.list_all(category=event.category)

        assert event.id in {e.id for e in events}

    async def test_filters_by_priority_exact(self, session):
        p1_event = await make_event(
            session, title='P1', priority=PriorityLevel.p1
        )
        p2_event = await make_event(
            session, title='P2', priority=PriorityLevel.p2
        )
        crud = ShowcaseCRUD(session)

        # limit выше дефолта: priority='П1' — не уникальный маркер, в общей
        # БД таких строк может быть больше 100, а наша свежесозданная не
        # обязательно попадёт в топ по published_at.
        events = await crud.list_all(priority='П1', limit=10_000)

        ids = {e.id for e in events}
        assert p1_event.id in ids
        assert p2_event.id not in ids

    async def test_filters_by_region_substring(self, session):
        marker = f'Регион-{uuid4().hex[:8]}'
        event = await make_event(session, title='A', region=marker)
        await make_event(session, title='B', region='Другой регион')
        crud = ShowcaseCRUD(session)

        events = await crud.list_all(region=marker)

        assert {e.id for e in events} == {event.id}

    async def test_filters_by_competitor_substring(self, session):
        marker = f'Конкурент-{uuid4().hex[:8]}'
        event = await make_event(session, title='A', competitor_name=marker)
        await make_event(session, title='B')
        crud = ShowcaseCRUD(session)

        events = await crud.list_all(competitor=marker)

        assert {e.id for e in events} == {event.id}

    async def test_filters_by_department_exact(self, session):
        marker = f'__тест-отдел-{uuid4().hex[:8]}__'
        event = await make_event(session, title='A', department_name=marker)
        await make_event(session, title='B')
        crud = ShowcaseCRUD(session)

        events = await crud.list_all(department=marker)

        assert {e.id for e in events} == {event.id}

    async def test_filters_by_published_date_range(self, session):
        early = await make_event(
            session, title='Early', published_at=date(2026, 1, 1)
        )
        late = await make_event(
            session, title='Late', published_at=date(2026, 12, 31)
        )
        crud = ShowcaseCRUD(session)

        events = await crud.list_all(
            published_from=date(2026, 1, 1),
            published_to=date(2026, 6, 1),
            limit=10_000,
        )

        ids = {e.id for e in events}
        assert early.id in ids
        assert late.id not in ids
