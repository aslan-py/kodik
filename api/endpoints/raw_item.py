"""raw_item (BP-1): только просмотр. GET '' (фильтры), GET '/{id}'.

Доступ — только analyst/admin (внутренняя механика пайплайна, не для
viewer/отделов, см. api/FASTAPI_PLAN.md, раздел 6).
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from api.dependencies import SessionDep, require_role
from api.responses import REFERENCE_DETAIL_RESPONSES, REFERENCE_LIST_RESPONSES
from api.schemas.raw_item import RawItemRead
from api.service.pipeline_view import RawItemService
from core.enums import RawItemStatus, UserRole

router = APIRouter()
_editor_only = [Depends(require_role(UserRole.analyst, UserRole.admin))]


@router.get(
    '',
    response_model=list[RawItemRead],
    responses=REFERENCE_LIST_RESPONSES,
    dependencies=_editor_only,
    summary='Список сырых результатов парсинга (raw_item)',
    description=(
        'Доступ: только `analyst` и `admin`. Фильтры: `status`, '
        '`search_task_id` — точное совпадение; `created_from/to`, '
        '`updated_from/to` — диапазон дат (включительно).'
    ),
)
async def list_raw_items(
    session: SessionDep,
    status: RawItemStatus | None = None,
    search_task_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[RawItemRead]:
    items = await RawItemService(session).list_items(
        status=status,
        search_task_id=search_task_id,
        created_from=created_from,
        created_to=created_to,
        updated_from=updated_from,
        updated_to=updated_to,
        limit=limit,
        offset=offset,
    )
    return [RawItemRead.model_validate(i) for i in items]


@router.get(
    '/{item_id}',
    response_model=RawItemRead,
    responses=REFERENCE_DETAIL_RESPONSES,
    dependencies=_editor_only,
    summary='raw_item по id',
    description='Доступ: только `analyst` и `admin`.',
)
async def read_raw_item(item_id: int, session: SessionDep) -> RawItemRead:
    item = await RawItemService(session).get_item(item_id)
    return RawItemRead.model_validate(item)
