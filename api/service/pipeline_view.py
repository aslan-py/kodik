"""Read-only сервисы данных пайплайна (BP-1/2/3/5): 404 + model_validate.

Тонкая обёртка над api/crud/pipeline_view.py — та же логика, что
ShowcaseService для list/get, но без мутаций (эти таблицы либо "грязное"
сырьё, либо неизменяемый журнал, см. api/FASTAPI_PLAN.md, раздел 6).
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.pipeline_view import (
    AlertCRUD,
    CategorizedEventCRUD,
    NormalizedItemCRUD,
    RawItemCRUD,
)


class RawItemService:
    def __init__(self, session: AsyncSession):
        self.crud = RawItemCRUD(session)

    async def list_items(self, **filters):
        return await self.crud.list_all(**filters)

    async def get_item(self, item_id: int):
        item = await self.crud.get(item_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'raw_item не найден')
        return item


class NormalizedItemService:
    def __init__(self, session: AsyncSession):
        self.crud = NormalizedItemCRUD(session)

    async def list_items(self, **filters):
        return await self.crud.list_all(**filters)

    async def get_item(self, item_id: int):
        item = await self.crud.get(item_id)
        if item is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, 'normalized_item не найден'
            )
        return item


class CategorizedEventService:
    def __init__(self, session: AsyncSession):
        self.crud = CategorizedEventCRUD(session)

    async def list_items(self, **filters):
        return await self.crud.list_all(**filters)

    async def get_item(self, item_id: int):
        item = await self.crud.get(item_id)
        if item is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, 'categorized_event не найден'
            )
        return item


class AlertService:
    def __init__(self, session: AsyncSession):
        self.crud = AlertCRUD(session)

    async def list_items(self, **filters):
        return await self.crud.list_all(**filters)

    async def get_item(self, item_id: int):
        item = await self.crud.get(item_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, 'alert не найден')
        return item
