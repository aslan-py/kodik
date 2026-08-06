"""Фабрика роутеров для справочников группы «Администрирование».

build_reference_router(...) собирает пять стандартных путей (GET list, GET
detail, POST, PATCH, DELETE=soft-delete) над произвольной моделью
Mixin[+ActiveMixin] — api/FASTAPI_PLAN.md, раздел 6. Под каждую таблицу
нужен только файл со схемами + один вызов этой фабрики
(см. api/endpoints/competitor.py и соседние).

Query-параметр поиска всегда называется `q` (не `name`/`keyword`/`domain` по
месту) — осознанное упрощение: фабрика одна на 13 таблиц, а не подменяет
сигнатуру FastAPI ради косметики параметра. Что именно ищет `q` —
документируется в description через search_field.

public_read=True — GET-роуты без EditorDep (только для department:
department_id выбирается ДО логина при регистрации и в профиле pending-
пользователя, см. api/endpoints/department.py). Доступ проверяется через
dependencies=[...] на самом декораторе, а не как параметр функции — так
сигнатура GET-обработчиков не зависит от public_read.

soft_delete=False — нет DELETE и фильтр is_active не имеет смысла (только
для region: статический справочник городов, "выключать" нечего;
ReferenceCRUD.list_all сам игнорирует is_active для моделей без этого поля).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import SessionDep, require_role
from api.responses import (
    PUBLIC_DETAIL_RESPONSES,
    PUBLIC_LIST_RESPONSES,
    REFERENCE_DETAIL_RESPONSES,
    REFERENCE_LIST_RESPONSES,
    REFERENCE_WRITE_RESPONSES,
)
from api.service.reference import ReferenceService
from core.enums import UserRole

_editor_only = [Depends(require_role(UserRole.analyst, UserRole.admin))]


def build_reference_router(
    model: type,
    *,
    read_schema: type[BaseModel],
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    search_field: str | None,
    not_found_message: str,
    tag: str,
    public_read: bool = False,
    soft_delete: bool = True,
) -> APIRouter:
    router = APIRouter()

    q_note = (
        f' `q` — подстрока без учёта регистра по полю `{search_field}`.'
        if search_field
        else ''
    )
    list_dependencies = [] if public_read else _editor_only
    list_responses = (
        PUBLIC_LIST_RESPONSES if public_read else REFERENCE_LIST_RESPONSES
    )
    detail_responses = (
        PUBLIC_DETAIL_RESPONSES if public_read else REFERENCE_DETAIL_RESPONSES
    )
    access_note = (
        'Доступ: публично, без токена.'
        if public_read
        else 'Доступ: только `analyst` и `admin`.'
    )

    @router.get(
        '',
        response_model=list[read_schema],
        responses=list_responses,
        dependencies=list_dependencies,
        summary=f'Список: {tag}',
        description=f'{access_note}{q_note}',
    )
    async def list_items(
        session: SessionDep,
        is_active: bool | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[read_schema]:
        service = ReferenceService(session, model, not_found_message)
        items = await service.list_items(
            is_active=is_active,
            search_field=search_field,
            search_value=q,
            limit=limit,
            offset=offset,
        )
        return [read_schema.model_validate(i) for i in items]

    @router.get(
        '/{item_id}',
        response_model=read_schema,
        responses=detail_responses,
        dependencies=list_dependencies,
        summary=f'{tag} по id',
        description=access_note,
    )
    async def get_item(item_id: int, session: SessionDep) -> read_schema:
        service = ReferenceService(session, model, not_found_message)
        item = await service.get_item(item_id)
        return read_schema.model_validate(item)

    @router.post(
        '',
        response_model=read_schema,
        status_code=201,
        responses=REFERENCE_WRITE_RESPONSES,
        dependencies=_editor_only,
        summary=f'Создать: {tag}',
        description='Доступ: только `analyst` и `admin`.',
    )
    async def create_item(
        data: create_schema, session: SessionDep
    ) -> read_schema:
        service = ReferenceService(session, model, not_found_message)
        item = await service.create_item(data.model_dump())
        return read_schema.model_validate(item)

    @router.patch(
        '/{item_id}',
        response_model=read_schema,
        responses=REFERENCE_WRITE_RESPONSES,
        dependencies=_editor_only,
        summary=f'Править: {tag}',
        description='Доступ: только `analyst` и `admin`. Partial update.',
    )
    async def update_item(
        item_id: int, data: update_schema, session: SessionDep
    ) -> read_schema:
        service = ReferenceService(session, model, not_found_message)
        changes = data.model_dump(exclude_unset=True)
        item = await service.update_item(item_id, changes)
        return read_schema.model_validate(item)

    if soft_delete:

        @router.delete(
            '/{item_id}',
            response_model=read_schema,
            responses=REFERENCE_WRITE_RESPONSES,
            dependencies=_editor_only,
            summary=f'Мягко выключить: {tag}',
            description=(
                'Доступ: только `analyst` и `admin`. Мягкое удаление '
                '(`is_active=false`), строка физически не удаляется. '
                'Восстановление — `PATCH` с `is_active=true`.'
            ),
        )
        async def delete_item(item_id: int, session: SessionDep) -> read_schema:
            service = ReferenceService(session, model, not_found_message)
            item = await service.soft_delete_item(item_id)
            return read_schema.model_validate(item)

    return router
