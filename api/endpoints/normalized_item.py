"""normalized_item (BP-2): только просмотр. GET '' (фильтры), GET '/{id}'.

Доступ — только analyst/admin (внутренняя механика пайплайна, не для
viewer/отделов, см. api/FASTAPI_PLAN.md, раздел 6).
"""

from datetime import date

from fastapi import APIRouter, Depends

from api.dependencies import SessionDep, require_role
from api.responses import REFERENCE_DETAIL_RESPONSES, REFERENCE_LIST_RESPONSES
from api.schemas.normalized_item import NormalizedItemRead
from api.service.pipeline_view import NormalizedItemService
from core.enums import NormStatus, RejectReason, UserRole

router = APIRouter()
_editor_only = [Depends(require_role(UserRole.analyst, UserRole.admin))]


@router.get(
    '',
    response_model=list[NormalizedItemRead],
    responses=REFERENCE_LIST_RESPONSES,
    dependencies=_editor_only,
    summary='Список нормализованных событий (normalized_item)',
    description=(
        'Доступ: только `analyst` и `admin`. Фильтры: `status`, '
        '`reject_reason`, `competitor_id`, `region_id` — точное совпадение; '
        '`published_from/to` — диапазон дат; `title` — подстрока без учёта '
        'регистра.'
    ),
)
async def list_normalized_items(
    session: SessionDep,
    status: NormStatus | None = None,
    reject_reason: RejectReason | None = None,
    competitor_id: int | None = None,
    region_id: int | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
    title: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[NormalizedItemRead]:
    items = await NormalizedItemService(session).list_items(
        status=status,
        reject_reason=reject_reason,
        competitor_id=competitor_id,
        region_id=region_id,
        published_from=published_from,
        published_to=published_to,
        title=title,
        limit=limit,
        offset=offset,
    )
    return [NormalizedItemRead.model_validate(i) for i in items]


@router.get(
    '/{item_id}',
    response_model=NormalizedItemRead,
    responses=REFERENCE_DETAIL_RESPONSES,
    dependencies=_editor_only,
    summary='normalized_item по id',
    description='Доступ: только `analyst` и `admin`.',
)
async def read_normalized_item(
    item_id: int, session: SessionDep
) -> NormalizedItemRead:
    item = await NormalizedItemService(session).get_item(item_id)
    return NormalizedItemRead.model_validate(item)
