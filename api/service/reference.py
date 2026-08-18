"""Generic-сервис для справочников группы «Администрирование».

Один класс на все 13 таблиц (api/FASTAPI_PLAN.md, раздел 6): 404 на
отсутствующий id, commit, и — самое нетривиальное — различение НА КАКОЙ
именно constraint упал INSERT/UPDATE. IntegrityError от asyncpg заворачивает
исходное исключение в exc.orig.__cause__: ForeignKeyViolationError — значит
один из переданных *_id не существует (404, а не «конфликт»), иначе —
нарушен unique/UniqueConstraint (409, значение уже занято). Одна проверка
закрывает и простой unique=True, и составные UniqueConstraint (stop_word,
routing_rule), и битые FK (search_task.competitor_id и т.п.) — без ручных
проверок существования на каждую таблицу.
"""

from asyncpg.exceptions import ForeignKeyViolationError
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.reference import ReferenceCRUD


class ReferenceService:
    def __init__(
        self, session: AsyncSession, model: type, not_found_message: str
    ):
        self.session = session
        self.crud = ReferenceCRUD(session, model)
        self._not_found = HTTPException(
            status.HTTP_404_NOT_FOUND, not_found_message
        )

    async def list_items(
        self,
        *,
        is_active: bool | None = None,
        search_field: str | None = None,
        search_value: str | None = None,
        filters: dict | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        return await self.crud.list_all(
            is_active=is_active,
            search_field=search_field,
            search_value=search_value,
            filters=filters,
            limit=limit,
            offset=offset,
        )

    async def get_item(self, item_id: int):
        item = await self.crud.get(item_id)
        if item is None:
            raise self._not_found
        return item

    async def create_item(self, data: dict):
        try:
            item = await self.crud.create(data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._map_integrity_error(exc) from exc
        return item

    async def update_item(self, item_id: int, changes: dict):
        item = await self.get_item(item_id)
        if not changes:
            return item
        try:
            item = await self.crud.update(item, changes)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._map_integrity_error(exc) from exc
        return item

    async def soft_delete_item(self, item_id: int):
        item = await self.get_item(item_id)
        item = await self.crud.soft_delete(item)
        await self.session.commit()
        return item

    @staticmethod
    def _map_integrity_error(exc: IntegrityError) -> HTTPException:
        """flush()/commit() внутри create_item/update_item ловятся здесь —
        нарушение constraint видно только в момент отправки SQL в БД, не
        раньше."""
        if isinstance(exc.orig.__cause__, ForeignKeyViolationError):
            return HTTPException(
                status.HTTP_404_NOT_FOUND, 'Один из указанных id не найден'
            )
        return HTTPException(status.HTTP_409_CONFLICT, 'Значение уже занято')
