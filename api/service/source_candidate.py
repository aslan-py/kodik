"""Read-only сервис source_candidate (BP-7): 404 + список с фильтрами."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.source_candidate import SourceCandidateCRUD


class SourceCandidateService:
    def __init__(self, session: AsyncSession):
        self.crud = SourceCandidateCRUD(session)

    async def list_items(self, **filters):
        return await self.crud.list_all(**filters)

    async def get_item(self, item_id: int):
        item = await self.crud.get(item_id)
        if item is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, 'Кандидат в источники не найден'
            )
        return item
