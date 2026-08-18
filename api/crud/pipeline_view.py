"""Read-only репозитории данных пайплайна (BP-1/2/3/5) для API.

Четыре маленьких класса одной формы (get + list_all с явными фильтрами) —
собраны в одном файле, а не разнесены по api/crud/<table>.py, т.к. они
чисто read-only (нет create/update/soft_delete) и слишком разные по
фильтрам, чтобы тянуть в generic ReferenceCRUD (api/FASTAPI_PLAN.md,
раздел 6, группа «Данные после парсинга/нормализации/LLM/уведомлений»).
Сессия — в self.session (через __init__), commit не нужен — только чтение.
"""

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import (
    AlertStatus,
    DeliveryMode,
    NormStatus,
    PriorityLevel,
    RawItemStatus,
    RejectReason,
)
from src.bp1.models import RawItem
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent
from src.bp5.models import Alert


class RawItemCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, item_id: int) -> RawItem | None:
        return await self.session.get(RawItem, item_id)

    async def list_all(
        self,
        status: RawItemStatus | None = None,
        search_task_id: int | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[RawItem]:
        stmt = select(RawItem)
        if status is not None:
            stmt = stmt.where(RawItem.status == status)
        if search_task_id is not None:
            stmt = stmt.where(RawItem.search_task_id == search_task_id)
        if created_from is not None:
            stmt = stmt.where(RawItem.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(RawItem.created_at <= created_to)
        if updated_from is not None:
            stmt = stmt.where(RawItem.updated_at >= updated_from)
        if updated_to is not None:
            stmt = stmt.where(RawItem.updated_at <= updated_to)
        stmt = stmt.order_by(RawItem.id.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class NormalizedItemCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, item_id: int) -> NormalizedItem | None:
        return await self.session.get(NormalizedItem, item_id)

    async def list_all(
        self,
        status: NormStatus | None = None,
        reject_reason: RejectReason | None = None,
        competitor_id: int | None = None,
        region_id: int | None = None,
        published_from: date | None = None,
        published_to: date | None = None,
        title: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[NormalizedItem]:
        stmt = select(NormalizedItem)
        if status is not None:
            stmt = stmt.where(NormalizedItem.status == status)
        if reject_reason is not None:
            stmt = stmt.where(NormalizedItem.reject_reason == reject_reason)
        if competitor_id is not None:
            stmt = stmt.where(NormalizedItem.competitor_id == competitor_id)
        if region_id is not None:
            stmt = stmt.where(NormalizedItem.region_id == region_id)
        if published_from is not None:
            stmt = stmt.where(NormalizedItem.published_at >= published_from)
        if published_to is not None:
            stmt = stmt.where(NormalizedItem.published_at <= published_to)
        if title is not None:
            stmt = stmt.where(NormalizedItem.title.ilike(f'%{title}%'))
        stmt = (
            stmt.order_by(NormalizedItem.id.desc()).limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class CategorizedEventCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, item_id: int) -> CategorizedEvent | None:
        return await self.session.get(CategorizedEvent, item_id)

    async def list_all(
        self,
        priority: PriorityLevel | None = None,
        category_id: int | None = None,
        department_id: int | None = None,
        categorized_from: datetime | None = None,
        categorized_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[CategorizedEvent]:
        stmt = select(CategorizedEvent)
        if priority is not None:
            stmt = stmt.where(CategorizedEvent.priority == priority)
        if category_id is not None:
            stmt = stmt.where(CategorizedEvent.category_id == category_id)
        if department_id is not None:
            stmt = stmt.where(CategorizedEvent.department_id == department_id)
        if categorized_from is not None:
            stmt = stmt.where(
                CategorizedEvent.categorized_at >= categorized_from
            )
        if categorized_to is not None:
            stmt = stmt.where(CategorizedEvent.categorized_at <= categorized_to)
        stmt = (
            stmt.order_by(CategorizedEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class AlertCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, item_id: int) -> Alert | None:
        return await self.session.get(Alert, item_id)

    async def list_all(
        self,
        status: AlertStatus | None = None,
        channel_id: int | None = None,
        user_id: int | None = None,
        priority: PriorityLevel | None = None,
        mode: DeliveryMode | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        sent_from: datetime | None = None,
        sent_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Alert]:
        stmt = select(Alert)
        if status is not None:
            stmt = stmt.where(Alert.status == status)
        if channel_id is not None:
            stmt = stmt.where(Alert.channel_id == channel_id)
        if user_id is not None:
            stmt = stmt.where(Alert.user_id == user_id)
        if priority is not None:
            stmt = stmt.where(Alert.priority == priority)
        if mode is not None:
            stmt = stmt.where(Alert.mode == mode)
        if created_from is not None:
            stmt = stmt.where(Alert.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(Alert.created_at <= created_to)
        if sent_from is not None:
            stmt = stmt.where(Alert.sent_at >= sent_from)
        if sent_to is not None:
            stmt = stmt.where(Alert.sent_at <= sent_to)
        stmt = stmt.order_by(Alert.id.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()
