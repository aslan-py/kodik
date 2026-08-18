"""Бизнес-логика плана действий BP-6 (`action_item`): видимость по своему
отделу для viewer, полный доступ для analyst/admin.

Роутер (api/endpoints/action_items.py) только вызывает методы
ActionItemService — вся логика (фильтрация по отделу, разграничение
правки, HTTPException, commit) живёт здесь.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.action_items import ActionItemCRUD
from api.schemas.action_items import (
    ActionItemCreate,
    ActionItemRead,
    ActionItemUpdate,
)
from core.enums import ActionStatus, UserRole
from src.bp5.models import User

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, 'Задача не найдена')
_VIEWER_EDITABLE_FIELDS = {'status', 'expected_result'}


class ActionItemService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = ActionItemCRUD(session)

    async def list_items(
        self,
        user: User,
        department_id: int | None = None,
        status_filter: ActionStatus | None = None,
        task: str | None = None,
        assigned_user_id: int | None = None,
        showcase_event_id: int | None = None,
        deadline_from: date | None = None,
        deadline_to: date | None = None,
        priority: str | None = None,
    ) -> list[ActionItemRead]:
        """viewer видит только задачи своего отдела (весь отдел, не
        только те, где он assigned_user_id — так решили: отдел в целом
        отвечает за результат) — department_id из query для viewer
        игнорируется и подменяется его собственным. analyst/admin — весь
        список, с любыми из фильтров."""
        if user.role == UserRole.viewer:
            if user.department_id is None:
                return []
            department_id = user.department_id
        items = await self.crud.list_all(
            department_id,
            status_filter,
            task,
            assigned_user_id,
            showcase_event_id,
            deadline_from,
            deadline_to,
            priority,
        )
        return [ActionItemRead.model_validate(i) for i in items]

    async def get_item(self, user: User, item_id: int) -> ActionItemRead:
        item = await self.crud.get(item_id)
        if item is None:
            raise _NOT_FOUND
        if (
            user.role == UserRole.viewer
            and item.department_id != user.department_id
        ):
            # 404, не 403 — не подтверждаем существование чужих задач по id.
            raise _NOT_FOUND
        return ActionItemRead.model_validate(item)

    async def create_item(self, data: ActionItemCreate) -> ActionItemRead:
        """Вызывается только из-под EditorDep (analyst/admin) — роль
        здесь повторно не проверяется."""
        if not await self.crud.showcase_event_exists(data.showcase_event_id):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f'Событие витрины с id={data.showcase_event_id} не найдено',
            )
        if not await self.crud.department_exists(data.department_id):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f'Отдел с id={data.department_id} не найден',
            )
        if data.assigned_user_id is not None:
            await self._check_assigned_user(
                data.assigned_user_id, data.department_id
            )

        item = await self.crud.create(data)
        await self.session.commit()
        return ActionItemRead.model_validate(item)

    async def update_item(
        self, user: User, item_id: int, data: ActionItemUpdate
    ) -> ActionItemRead:
        item = await self.crud.get(item_id)
        if item is None:
            raise _NOT_FOUND
        if (
            user.role == UserRole.viewer
            and item.department_id != user.department_id
        ):
            raise _NOT_FOUND

        changes = data.model_dump(exclude_unset=True)
        if user.role == UserRole.viewer:
            # Непозволенные для viewer поля молча отбрасываются — один
            # эндпоинт на обе роли, а не 422 на «чужое» поле.
            changes = {
                k: v for k, v in changes.items() if k in _VIEWER_EDITABLE_FIELDS
            }
            if not changes:
                return ActionItemRead.model_validate(item)

        if 'department_id' in changes and not await self.crud.department_exists(
            changes['department_id']
        ):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f'Отдел с id={changes["department_id"]} не найден',
            )

        if changes.get('assigned_user_id') is not None:
            target_department_id = changes.get(
                'department_id', item.department_id
            )
            await self._check_assigned_user(
                changes['assigned_user_id'], target_department_id
            )

        item = await self.crud.update(item, changes)
        await self.session.commit()
        return ActionItemRead.model_validate(item)

    async def _check_assigned_user(
        self, assigned_user_id: int, department_id: int
    ) -> None:
        assigned_user = await self.crud.get_user(assigned_user_id)
        if assigned_user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f'Пользователь с id={assigned_user_id} не найден',
            )
        if assigned_user.department_id != department_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                'assigned_user_id не состоит в указанном department_id',
            )
