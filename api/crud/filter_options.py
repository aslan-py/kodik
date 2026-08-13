"""SQL-запросы доступных значений фильтров."""

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bp3.models import Department
from src.bp4.models import ShowcaseEvent
from src.bp5.models import User
from src.bp6.models import ActionItem


class FilterOptionsCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def showcase_values(self, column: Any) -> Sequence[str]:
        stmt = (
            select(column)
            .where(column.is_not(None), func.btrim(column) != '')
            .group_by(column)
            .order_by(func.lower(column), column)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def _scope(stmt: Select, department_id: int | None) -> Select:
        if department_id is not None:
            return stmt.where(ActionItem.department_id == department_id)
        return stmt

    async def action_deadlines(
        self, department_id: int | None = None
    ) -> Sequence[date]:
        stmt = (
            select(ActionItem.deadline)
            .distinct()
            .where(ActionItem.deadline.is_not(None))
        )
        stmt = self._scope(stmt, department_id).order_by(ActionItem.deadline)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def action_priorities(
        self,
        allowed: Sequence[str],
        department_id: int | None = None,
    ) -> Sequence[str]:
        stmt = (
            select(ShowcaseEvent.priority)
            .join(
                ActionItem,
                ActionItem.showcase_event_id == ShowcaseEvent.id,
            )
            .distinct()
            .where(ShowcaseEvent.priority.in_(allowed))
        )
        stmt = self._scope(stmt, department_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def assigned_users(
        self, department_id: int | None = None
    ) -> Sequence[tuple[int, str]]:
        label = func.coalesce(User.full_name, User.email)
        stmt = (
            select(User.id, label.label('label'))
            .join(ActionItem, ActionItem.assigned_user_id == User.id)
            .group_by(User.id, label)
        )
        stmt = self._scope(stmt, department_id).order_by(
            func.lower(label), label, User.id
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def departments(
        self, department_id: int | None = None
    ) -> Sequence[tuple[int, str]]:
        stmt = (
            select(Department.id, Department.name)
            .join(ActionItem, ActionItem.department_id == Department.id)
            .group_by(Department.id, Department.name)
        )
        stmt = self._scope(stmt, department_id).order_by(
            func.lower(Department.name), Department.name, Department.id
        )
        result = await self.session.execute(stmt)
        return result.all()
