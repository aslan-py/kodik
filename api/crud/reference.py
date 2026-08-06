"""Generic-репозиторий для справочников с одинаковой формой (Mixin+ActiveMixin).

Один класс на все таблицы группы «Администрирование» (api/FASTAPI_PLAN.md,
раздел 6) вместо повторения одного и того же CRUD 13 раз. Сессия — в
self.session (через __init__), commit делает вызывающий сервис
(api/service/reference.py) — здесь только запросы и flush.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ReferenceCRUD:
    """Репозиторий над произвольной моделью Mixin[+ActiveMixin]."""

    def __init__(self, session: AsyncSession, model: type):
        self.session = session
        self.model = model

    async def get(self, item_id: int):
        return await self.session.get(self.model, item_id)

    async def list_all(
        self,
        *,
        is_active: bool | None = None,
        search_field: str | None = None,
        search_value: str | None = None,
        filters: dict | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence:
        """Список с опциональными фильтрами (все — AND).

        is_active — точное совпадение, если у модели есть это поле (region —
        статический справочник без ActiveMixin, фильтр для неё молча
        игнорируется, а не падает AttributeError). search_field/search_value
        — ilike по одному сконфигурированному строковому полю (см.
        build_reference_router). filters — точное совпадение по произвольным
        полям (напр. search_task: competitor_id/source_id/trigger_id) — для
        случаев вне generic-фабрики.
        """
        stmt = select(self.model)
        if is_active is not None and hasattr(self.model, 'is_active'):
            stmt = stmt.where(self.model.is_active == is_active)
        if search_field is not None and search_value is not None:
            column = getattr(self.model, search_field)
            stmt = stmt.where(column.ilike(f'%{search_value}%'))
        for field, value in (filters or {}).items():
            stmt = stmt.where(getattr(self.model, field) == value)
        stmt = stmt.order_by(self.model.id).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, data: dict):
        item = self.model(**data)
        self.session.add(item)
        await self.session.flush()
        return item

    async def update(self, item, changes: dict):
        for field, value in changes.items():
            setattr(item, field, value)
        await self.session.flush()
        return item

    async def soft_delete(self, item):
        item.is_active = False
        await self.session.flush()
        return item
