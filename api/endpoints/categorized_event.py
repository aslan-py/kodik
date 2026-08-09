"""categorized_event (BP-3): только просмотр. GET '' (фильтры), GET '/{id}'.

Правка разметки — через `PATCH /showcase/{id}`, не здесь (см.
api/schemas/categorized_event.py). Доступ — только analyst/admin.
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from api.dependencies import SessionDep, require_role
from api.responses import REFERENCE_DETAIL_RESPONSES, REFERENCE_LIST_RESPONSES
from api.schemas.categorized_event import CategorizedEventRead
from api.service.pipeline_view import CategorizedEventService
from core.enums import PriorityLevel, UserRole

router = APIRouter()
_editor_only = [Depends(require_role(UserRole.analyst, UserRole.admin))]


@router.get(
    '',
    response_model=list[CategorizedEventRead],
    responses=REFERENCE_LIST_RESPONSES,
    dependencies=_editor_only,
    summary='Список размеченных событий (categorized_event)',
    description=(
        'Доступ: только `analyst` и `admin`. Фильтры: `priority`, '
        '`category_id`, `department_id` — точное совпадение; '
        '`categorized_from/to` — диапазон дат.'
    ),
)
async def list_categorized_events(
    session: SessionDep,
    priority: PriorityLevel | None = None,
    category_id: int | None = None,
    department_id: int | None = None,
    categorized_from: datetime | None = None,
    categorized_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[CategorizedEventRead]:
    items = await CategorizedEventService(session).list_items(
        priority=priority,
        category_id=category_id,
        department_id=department_id,
        categorized_from=categorized_from,
        categorized_to=categorized_to,
        limit=limit,
        offset=offset,
    )
    return [CategorizedEventRead.model_validate(i) for i in items]


@router.get(
    '/{item_id}',
    response_model=CategorizedEventRead,
    responses=REFERENCE_DETAIL_RESPONSES,
    dependencies=_editor_only,
    summary='categorized_event по id',
    description='Доступ: только `analyst` и `admin`.',
)
async def read_categorized_event(
    item_id: int, session: SessionDep
) -> CategorizedEventRead:
    item = await CategorizedEventService(session).get_item(item_id)
    return CategorizedEventRead.model_validate(item)
