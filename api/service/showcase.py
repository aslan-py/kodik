"""Бизнес-логика витрины BP-4: список, детали, write-through правка.

Роутер (api/endpoints/showcase.py) только вызывает методы ShowcaseService.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.showcase import ShowcaseCRUD
from api.schemas.showcase import ShowcaseEventRead, ShowcaseEventUpdate

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, 'Событие не найдено')


class ShowcaseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = ShowcaseCRUD(session)

    async def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        title: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        region: str | None = None,
        competitor: str | None = None,
        department: str | None = None,
        media: str | None = None,
        published_from: date | None = None,
        published_to: date | None = None,
    ) -> list[ShowcaseEventRead]:
        events = await self.crud.list_all(
            limit=limit,
            offset=offset,
            title=title,
            category=category,
            priority=priority,
            region=region,
            competitor=competitor,
            department=department,
            media=media,
            published_from=published_from,
            published_to=published_to,
        )
        return [ShowcaseEventRead.model_validate(e) for e in events]

    async def get_event(self, showcase_id: int) -> ShowcaseEventRead:
        event = await self.crud.get(showcase_id)
        if event is None:
            raise _NOT_FOUND
        return ShowcaseEventRead.model_validate(event)

    async def update_event(
        self, showcase_id: int, data: ShowcaseEventUpdate
    ) -> ShowcaseEventRead:
        event = await self.crud.update(showcase_id, data)
        if event is None:
            raise _NOT_FOUND
        await self.session.commit()
        return ShowcaseEventRead.model_validate(event)
