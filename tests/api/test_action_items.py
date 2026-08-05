"""Тесты плана действий BP-6 (`action_item`): CRUD-слой + сервис
(видимость по отделу, разграничение правки viewer vs analyst/admin).

commit — no-op (см. tests/api/conftest.py::no_commit), как и в остальных
тестах tests/api/*.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.crud.action_items import ActionItemCRUD
from api.schemas.action_items import ActionItemCreate, ActionItemUpdate
from api.service.action_items import ActionItemService
from core.enums import (
    ActionStatus,
    NormStatus,
    PriorityLevel,
    RawItemStatus,
    TonalityLevel,
    UserRole,
)
from src.bp1.models import Competitor, RawItem, SearchTask, Source
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp4.constants import PRIORITY_DISPLAY
from src.bp4.models import ShowcaseEvent
from src.bp5.models import User


async def make_department(session) -> Department:
    d = Department(name=f'__тест-отдел-{uuid4().hex[:8]}__')
    session.add(d)
    await session.flush()
    return d


async def make_user(session, *, role, department_id=None) -> User:
    u = User(
        email=f'{uuid4().hex[:8]}@test.ru',
        password_hash='test-hash',
        role=role,
        department_id=department_id,
    )
    session.add(u)
    await session.flush()
    return u


async def make_showcase_event(session, *, title='Событие') -> ShowcaseEvent:
    """Минимальная цепочка raw_item -> normalized_item -> categorized_event
    -> showcase_event (см. tests/bp5/test_crud.py::make_showcase — тот же
    контракт полей)."""
    competitor = Competitor(name=f'__тест-конкурент-{uuid4().hex[:8]}__')
    source = Source(name=f'__тест-источник-{uuid4().hex[:8]}__')
    category = Category(name=f'__тест-категория-{uuid4().hex[:8]}__')
    session.add_all([competitor, source, category])
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
        published_at=date(2026, 6, 25),
        title=title,
        dedup_key=uuid4().hex,
        status=NormStatus.ok,
    )
    session.add(item)
    await session.flush()

    ce = CategorizedEvent(
        normalized_item_id=item.id,
        priority=PriorityLevel.p1,
        category_id=category.id,
        tonality=TonalityLevel.neutral,
        llm_model='test',
        prompt_version='v0',
    )
    session.add(ce)
    await session.flush()

    sc = ShowcaseEvent(
        categorized_event_id=ce.id,
        raw_item_id=raw.id,
        title=title,
        priority=PRIORITY_DISPLAY[PriorityLevel.p1],
        category=category.name,
        tonality='нейтральная',
    )
    session.add(sc)
    await session.flush()
    return sc


class TestActionItemCRUD:
    async def test_create_and_get(self, session):
        department = await make_department(session)
        event = await make_showcase_event(session)
        crud = ActionItemCRUD(session)

        item = await crud.create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='Сделать X',
                department_id=department.id,
            )
        )

        fetched = await crud.get(item.id)
        assert fetched is not None
        assert fetched.task == 'Сделать X'
        assert fetched.status == ActionStatus.open

    async def test_list_all_filters_by_department(self, session):
        dep_a = await make_department(session)
        dep_b = await make_department(session)
        event_a = await make_showcase_event(session, title='A')
        event_b = await make_showcase_event(session, title='B')
        crud = ActionItemCRUD(session)
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_a.id, task='A', department_id=dep_a.id
            )
        )
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_b.id, task='B', department_id=dep_b.id
            )
        )

        items = await crud.list_all(department_id=dep_a.id)

        assert {i.showcase_event_id for i in items} == {event_a.id}

    async def test_list_all_filters_by_status(self, session):
        department = await make_department(session)
        event = await make_showcase_event(session)
        crud = ActionItemCRUD(session)
        item = await crud.create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=department.id,
            )
        )
        await crud.update(item, {'status': ActionStatus.done})

        open_items = await crud.list_all(
            department_id=department.id, status=ActionStatus.open
        )
        done_items = await crud.list_all(
            department_id=department.id, status=ActionStatus.done
        )

        assert item.id not in {i.id for i in open_items}
        assert item.id in {i.id for i in done_items}

    async def test_list_all_filters_by_task_substring(self, session):
        department = await make_department(session)
        event_a = await make_showcase_event(session, title='A')
        event_b = await make_showcase_event(session, title='B')
        crud = ActionItemCRUD(session)
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_a.id,
                task='Согласовать позицию с юристами',
                department_id=department.id,
            )
        )
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_b.id,
                task='Проверить отчёт маркетинга',
                department_id=department.id,
            )
        )

        items = await crud.list_all(task='юристами')

        assert {i.showcase_event_id for i in items} == {event_a.id}

    async def test_list_all_filters_by_assigned_user(self, session):
        department = await make_department(session)
        user_a = await make_user(
            session, role=UserRole.viewer, department_id=department.id
        )
        user_b = await make_user(
            session, role=UserRole.viewer, department_id=department.id
        )
        event_a = await make_showcase_event(session, title='A')
        event_b = await make_showcase_event(session, title='B')
        crud = ActionItemCRUD(session)
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_a.id,
                task='A',
                department_id=department.id,
                assigned_user_id=user_a.id,
            )
        )
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_b.id,
                task='B',
                department_id=department.id,
                assigned_user_id=user_b.id,
            )
        )

        items = await crud.list_all(assigned_user_id=user_a.id)

        assert {i.showcase_event_id for i in items} == {event_a.id}

    async def test_list_all_filters_by_showcase_event_id(self, session):
        department = await make_department(session)
        event_a = await make_showcase_event(session, title='A')
        event_b = await make_showcase_event(session, title='B')
        crud = ActionItemCRUD(session)
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_a.id,
                task='A',
                department_id=department.id,
            )
        )
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_b.id,
                task='B',
                department_id=department.id,
            )
        )

        items = await crud.list_all(showcase_event_id=event_b.id)

        assert {i.showcase_event_id for i in items} == {event_b.id}

    async def test_update_changes_fields(self, session):
        department = await make_department(session)
        event = await make_showcase_event(session)
        crud = ActionItemCRUD(session)
        item = await crud.create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=department.id,
            )
        )

        updated = await crud.update(item, {'expected_result': 'Готово'})

        assert updated.expected_result == 'Готово'


class TestListItems:
    async def test_viewer_sees_only_own_department(self, session):
        own_department = await make_department(session)
        other_department = await make_department(session)
        viewer = await make_user(
            session, role=UserRole.viewer, department_id=own_department.id
        )
        own_event = await make_showcase_event(session, title='Own')
        other_event = await make_showcase_event(session, title='Other')
        crud = ActionItemCRUD(session)
        await crud.create(
            ActionItemCreate(
                showcase_event_id=own_event.id,
                task='Own task',
                department_id=own_department.id,
            )
        )
        await crud.create(
            ActionItemCreate(
                showcase_event_id=other_event.id,
                task='Other task',
                department_id=other_department.id,
            )
        )

        items = await ActionItemService(session).list_items(viewer)

        assert {i.showcase_event_id for i in items} == {own_event.id}

    async def test_viewer_without_department_sees_nothing(self, session):
        viewer = await make_user(session, role=UserRole.viewer)
        department = await make_department(session)
        event = await make_showcase_event(session)
        await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=department.id,
            )
        )

        items = await ActionItemService(session).list_items(viewer)

        assert items == []

    async def test_analyst_sees_all_departments(self, session):
        dep_a = await make_department(session)
        dep_b = await make_department(session)
        analyst = await make_user(session, role=UserRole.analyst)
        event_a = await make_showcase_event(session, title='A')
        event_b = await make_showcase_event(session, title='B')
        crud = ActionItemCRUD(session)
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_a.id, task='A', department_id=dep_a.id
            )
        )
        await crud.create(
            ActionItemCreate(
                showcase_event_id=event_b.id, task='B', department_id=dep_b.id
            )
        )

        items = await ActionItemService(session).list_items(analyst)

        assert {event_a.id, event_b.id} <= {i.showcase_event_id for i in items}


class TestGetItem:
    async def test_viewer_gets_404_for_other_department(self, session):
        own_department = await make_department(session)
        other_department = await make_department(session)
        viewer = await make_user(
            session, role=UserRole.viewer, department_id=own_department.id
        )
        event = await make_showcase_event(session)
        item = await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=other_department.id,
            )
        )

        with pytest.raises(HTTPException) as exc:
            await ActionItemService(session).get_item(viewer, item.id)

        assert exc.value.status_code == 404

    async def test_viewer_gets_own_department_item(self, session):
        department = await make_department(session)
        viewer = await make_user(
            session, role=UserRole.viewer, department_id=department.id
        )
        event = await make_showcase_event(session)
        item = await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=department.id,
            )
        )

        result = await ActionItemService(session).get_item(viewer, item.id)

        assert result.id == item.id


class TestCreateItem:
    async def test_success(self, session):
        department = await make_department(session)
        event = await make_showcase_event(session)

        result = await ActionItemService(session).create_item(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='Сделать X',
                department_id=department.id,
            )
        )

        assert result.task == 'Сделать X'
        assert result.status == ActionStatus.open

    async def test_unknown_showcase_event_404(self, session):
        department = await make_department(session)

        with pytest.raises(HTTPException) as exc:
            await ActionItemService(session).create_item(
                ActionItemCreate(
                    showcase_event_id=999_999,
                    task='X',
                    department_id=department.id,
                )
            )

        assert exc.value.status_code == 404

    async def test_unknown_department_404(self, session):
        event = await make_showcase_event(session)

        with pytest.raises(HTTPException) as exc:
            await ActionItemService(session).create_item(
                ActionItemCreate(
                    showcase_event_id=event.id,
                    task='X',
                    department_id=999_999,
                )
            )

        assert exc.value.status_code == 404

    async def test_assigned_user_department_mismatch_conflict(self, session):
        department = await make_department(session)
        other_department = await make_department(session)
        assigned_user = await make_user(
            session, role=UserRole.viewer, department_id=other_department.id
        )
        event = await make_showcase_event(session)

        with pytest.raises(HTTPException) as exc:
            await ActionItemService(session).create_item(
                ActionItemCreate(
                    showcase_event_id=event.id,
                    task='X',
                    department_id=department.id,
                    assigned_user_id=assigned_user.id,
                )
            )

        assert exc.value.status_code == 409


class TestUpdateItem:
    async def test_viewer_can_change_status_and_expected_result(self, session):
        department = await make_department(session)
        viewer = await make_user(
            session, role=UserRole.viewer, department_id=department.id
        )
        event = await make_showcase_event(session)
        item = await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=department.id,
            )
        )

        result = await ActionItemService(session).update_item(
            viewer,
            item.id,
            ActionItemUpdate(
                status=ActionStatus.in_progress, expected_result='Готово'
            ),
        )

        assert result.status == ActionStatus.in_progress
        assert result.expected_result == 'Готово'

    async def test_viewer_cannot_change_task(self, session):
        department = await make_department(session)
        viewer = await make_user(
            session, role=UserRole.viewer, department_id=department.id
        )
        event = await make_showcase_event(session)
        item = await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='Исходная задача',
                department_id=department.id,
            )
        )

        result = await ActionItemService(session).update_item(
            viewer, item.id, ActionItemUpdate(task='Подменённая задача')
        )

        assert result.task == 'Исходная задача'

    async def test_viewer_404_for_other_department(self, session):
        own_department = await make_department(session)
        other_department = await make_department(session)
        viewer = await make_user(
            session, role=UserRole.viewer, department_id=own_department.id
        )
        event = await make_showcase_event(session)
        item = await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=other_department.id,
            )
        )

        with pytest.raises(HTTPException) as exc:
            await ActionItemService(session).update_item(
                viewer, item.id, ActionItemUpdate(status=ActionStatus.done)
            )

        assert exc.value.status_code == 404

    async def test_analyst_can_change_any_field(self, session):
        department = await make_department(session)
        other_department = await make_department(session)
        analyst = await make_user(session, role=UserRole.analyst)
        event = await make_showcase_event(session)
        item = await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=department.id,
            )
        )

        result = await ActionItemService(session).update_item(
            analyst,
            item.id,
            ActionItemUpdate(
                task='Новая задача', department_id=other_department.id
            ),
        )

        assert result.task == 'Новая задача'
        assert result.department_id == other_department.id

    async def test_analyst_assigned_user_department_mismatch_conflict(
        self, session
    ):
        department = await make_department(session)
        other_department = await make_department(session)
        analyst = await make_user(session, role=UserRole.analyst)
        assigned_user = await make_user(
            session, role=UserRole.viewer, department_id=other_department.id
        )
        event = await make_showcase_event(session)
        item = await ActionItemCRUD(session).create(
            ActionItemCreate(
                showcase_event_id=event.id,
                task='X',
                department_id=department.id,
            )
        )

        with pytest.raises(HTTPException) as exc:
            await ActionItemService(session).update_item(
                analyst,
                item.id,
                ActionItemUpdate(assigned_user_id=assigned_user.id),
            )

        assert exc.value.status_code == 409
