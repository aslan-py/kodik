"""Сборка вариантов фильтров с учётом роли пользователя."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.filter_options import FilterOptionsCRUD
from api.schemas.filter_options import (
    ActionItemFilterOptions,
    FilterOptionsRead,
    IdLabelOption,
    ShowcaseFilterOptions,
)
from core.enums import ActionStatus, PriorityLevel, UserRole
from src.bp4.constants import PRIORITY_DISPLAY
from src.bp4.models import ShowcaseEvent
from src.bp5.models import User

PRIORITY_OPTIONS = [PRIORITY_DISPLAY[item] for item in PriorityLevel]


class FilterOptionsService:
    def __init__(self, session: AsyncSession):
        self.crud = FilterOptionsCRUD(session)

    async def get_options(self, user: User) -> FilterOptionsRead:
        showcase = ShowcaseFilterOptions(
            category=await self.crud.showcase_values(ShowcaseEvent.category),
            region=await self.crud.showcase_values(ShowcaseEvent.region),
            priority=PRIORITY_OPTIONS,
            competitor=await self.crud.showcase_values(
                ShowcaseEvent.competitor
            ),
            department=await self.crud.showcase_values(
                ShowcaseEvent.department
            ),
        )

        if user.role == UserRole.viewer and user.department_id is None:
            deadlines = []
            priorities = []
            users = []
            departments = []
        else:
            scope = user.department_id if user.role == UserRole.viewer else None
            deadlines = await self.crud.action_deadlines(scope)
            present_priorities = set(
                await self.crud.action_priorities(PRIORITY_OPTIONS, scope)
            )
            priorities = [
                value
                for value in PRIORITY_OPTIONS
                if value in present_priorities
            ]
            users = await self.crud.assigned_users(scope)
            departments = await self.crud.departments(scope)

        action_items = ActionItemFilterOptions(
            status=list(ActionStatus),
            deadline=list(deadlines),
            priority=priorities,
            assigned_user_id=[
                IdLabelOption(value=value, label=label)
                for value, label in users
            ],
            department_id=[
                IdLabelOption(value=value, label=label)
                for value, label in departments
            ],
        )
        return FilterOptionsRead(showcase=showcase, action_items=action_items)
