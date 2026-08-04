"""Репозиторий плана действий BP-6 (`action_item`) для API.

Сессия — в self.session (через __init__), методы её не принимают.
Транзакцией (commit) управляет вызывающий код (сервис из
api/service/action_items.py) — здесь только запросы и flush.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.action_items import ActionItemCreate
from core.enums import ActionStatus
from src.bp3.models import Department
from src.bp4.models import ShowcaseEvent
from src.bp5.models import User
from src.bp6.models import ActionItem


class ActionItemCRUD:
    """Репозиторий ActionItem: чтение (с фильтрами), создание, правка."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, item_id: int) -> ActionItem | None:
        return await self.session.get(ActionItem, item_id)

    async def list_all(
        self,
        department_id: int | None = None,
        status: ActionStatus | None = None,
        task: str | None = None,
        assigned_user_id: int | None = None,
        showcase_event_id: int | None = None,
    ) -> Sequence[ActionItem]:
        """Список задач с опциональными фильтрами (все — AND).

        task — подстрока без учёта регистра (ilike). Остальные — точное
        совпадение. showcase_event_id, в частности, удобен, чтобы
        проверить, заведена ли уже задача по конкретному событию.
        """
        stmt = select(ActionItem).order_by(ActionItem.id.desc())
        if department_id is not None:
            stmt = stmt.where(ActionItem.department_id == department_id)
        if status is not None:
            stmt = stmt.where(ActionItem.status == status)
        if task is not None:
            stmt = stmt.where(ActionItem.task.ilike(f'%{task}%'))
        if assigned_user_id is not None:
            stmt = stmt.where(ActionItem.assigned_user_id == assigned_user_id)
        if showcase_event_id is not None:
            stmt = stmt.where(ActionItem.showcase_event_id == showcase_event_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def showcase_event_exists(self, showcase_event_id: int) -> bool:
        return (
            await self.session.get(ShowcaseEvent, showcase_event_id)
        ) is not None

    async def department_exists(self, department_id: int) -> bool:
        return await self.session.get(Department, department_id) is not None

    async def get_user(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def create(self, data: ActionItemCreate) -> ActionItem:
        item = ActionItem(
            showcase_event_id=data.showcase_event_id,
            task=data.task,
            department_id=data.department_id,
            assigned_user_id=data.assigned_user_id,
            deadline=data.deadline,
            expected_result=data.expected_result,
            status=ActionStatus.open,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update(self, item: ActionItem, changes: dict) -> ActionItem:
        for field, value in changes.items():
            setattr(item, field, value)
        await self.session.flush()
        return item
