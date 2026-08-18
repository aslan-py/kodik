"""search_task (BP-1, матрица задач сбора): CRUD с точными фильтрами.

Не через build_reference_router — список фильтруется точным совпадением по
competitor_id/source_id/trigger_id (не ilike-`q`, как у остальных
справочников), остальное (get/create/update/soft_delete) переиспользует тот
же ReferenceService, что и generic-группа (api/service/reference.py).
"""

from fastapi import APIRouter, Depends

from api.dependencies import SessionDep, require_role
from api.responses import (
    REFERENCE_DETAIL_RESPONSES,
    REFERENCE_LIST_RESPONSES,
    REFERENCE_WRITE_RESPONSES,
)
from api.schemas.search_task import (
    SearchTaskCreate,
    SearchTaskRead,
    SearchTaskUpdate,
)
from api.service.reference import ReferenceService
from core.enums import UserRole
from src.bp1.models import SearchTask

router = APIRouter()

_NOT_FOUND = 'Задача сбора не найдена'
_editor_only = [Depends(require_role(UserRole.analyst, UserRole.admin))]


@router.get(
    '',
    response_model=list[SearchTaskRead],
    responses=REFERENCE_LIST_RESPONSES,
    dependencies=_editor_only,
    summary='Список: Задача сбора (search_task)',
    description=(
        'Доступ: только `analyst` и `admin`. Фильтры — точное совпадение: '
        '`competitor_id`, `source_id`, `trigger_id`, `is_active`.'
    ),
)
async def list_search_tasks(
    session: SessionDep,
    competitor_id: int | None = None,
    source_id: int | None = None,
    trigger_id: int | None = None,
    is_active: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SearchTaskRead]:
    filters = {
        k: v
        for k, v in {
            'competitor_id': competitor_id,
            'source_id': source_id,
            'trigger_id': trigger_id,
        }.items()
        if v is not None
    }
    service = ReferenceService(session, SearchTask, _NOT_FOUND)
    items = await service.list_items(
        is_active=is_active, filters=filters, limit=limit, offset=offset
    )
    return [SearchTaskRead.model_validate(i) for i in items]


@router.get(
    '/{item_id}',
    response_model=SearchTaskRead,
    responses=REFERENCE_DETAIL_RESPONSES,
    dependencies=_editor_only,
    summary='Задача сбора (search_task) по id',
    description='Доступ: только `analyst` и `admin`.',
)
async def read_search_task(item_id: int, session: SessionDep) -> SearchTaskRead:
    service = ReferenceService(session, SearchTask, _NOT_FOUND)
    item = await service.get_item(item_id)
    return SearchTaskRead.model_validate(item)


@router.post(
    '',
    response_model=SearchTaskRead,
    status_code=201,
    responses=REFERENCE_WRITE_RESPONSES,
    dependencies=_editor_only,
    summary='Создать: Задача сбора (search_task)',
    description=(
        'Доступ: только `analyst` и `admin`. 409 — такая комбинация '
        'competitor/source/trigger уже есть; 404 — id конкурента/источника/'
        'триггера не существует.'
    ),
)
async def create_search_task(
    data: SearchTaskCreate, session: SessionDep
) -> SearchTaskRead:
    service = ReferenceService(session, SearchTask, _NOT_FOUND)
    item = await service.create_item(data.model_dump())
    return SearchTaskRead.model_validate(item)


@router.patch(
    '/{item_id}',
    response_model=SearchTaskRead,
    responses=REFERENCE_WRITE_RESPONSES,
    dependencies=_editor_only,
    summary='Править: Задача сбора (search_task)',
    description=(
        'Доступ: только `analyst` и `admin`. Partial update: '
        '`is_active=false` деактивирует, `is_active=true` реактивирует '
        'задачу, а непереданные поля не меняются.'
    ),
)
async def update_search_task(
    item_id: int, data: SearchTaskUpdate, session: SessionDep
) -> SearchTaskRead:
    service = ReferenceService(session, SearchTask, _NOT_FOUND)
    changes = data.model_dump(exclude_unset=True)
    item = await service.update_item(item_id, changes)
    return SearchTaskRead.model_validate(item)


@router.delete(
    '/{item_id}',
    response_model=SearchTaskRead,
    responses=REFERENCE_WRITE_RESPONSES,
    dependencies=_editor_only,
    summary='Мягко выключить: Задача сбора (search_task)',
    description=(
        'Доступ: только `analyst` и `admin`. `is_active=false` — Celery '
        'Beat перестаёт брать задачу в перебор, строка не удаляется.'
    ),
)
async def delete_search_task(
    item_id: int, session: SessionDep
) -> SearchTaskRead:
    service = ReferenceService(session, SearchTask, _NOT_FOUND)
    item = await service.soft_delete_item(item_id)
    return SearchTaskRead.model_validate(item)
