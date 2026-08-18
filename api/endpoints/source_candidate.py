"""source_candidate (BP-7): только просмотр. GET '' (фильтры), GET '/{id}'.

Очередь кандидатов в источники — заполняет агент расширения (следующая
итерация), переносит в source SourceCandidatePromoter (src/bp7/pipeline.py)
по порогу score. Здесь только просмотр, без CRUD. Доступ — только
analyst/admin.
"""

from fastapi import APIRouter, Depends

from api.dependencies import SessionDep, require_role
from api.responses import REFERENCE_DETAIL_RESPONSES, REFERENCE_LIST_RESPONSES
from api.schemas.source_candidate import SourceCandidateRead
from api.service.source_candidate import SourceCandidateService
from core.enums import SourceCandidateStatus, UserRole

router = APIRouter()
_editor_only = [Depends(require_role(UserRole.analyst, UserRole.admin))]


@router.get(
    '',
    response_model=list[SourceCandidateRead],
    responses=REFERENCE_LIST_RESPONSES,
    dependencies=_editor_only,
    summary='Список кандидатов в источники (source_candidate)',
    description=(
        'Доступ: только `analyst` и `admin`. Фильтры: `status` '
        '(`new`/`promoted`), `competitor_id`, `is_active` — точное '
        'совпадение; `domain` — подстрока без учёта регистра.'
    ),
)
async def list_source_candidates(
    session: SessionDep,
    status: SourceCandidateStatus | None = None,
    competitor_id: int | None = None,
    is_active: bool | None = None,
    domain: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SourceCandidateRead]:
    items = await SourceCandidateService(session).list_items(
        status=status,
        competitor_id=competitor_id,
        is_active=is_active,
        domain=domain,
        limit=limit,
        offset=offset,
    )
    return [SourceCandidateRead.model_validate(i) for i in items]


@router.get(
    '/{item_id}',
    response_model=SourceCandidateRead,
    responses=REFERENCE_DETAIL_RESPONSES,
    dependencies=_editor_only,
    summary='source_candidate по id',
    description='Доступ: только `analyst` и `admin`.',
)
async def read_source_candidate(
    item_id: int, session: SessionDep
) -> SourceCandidateRead:
    item = await SourceCandidateService(session).get_item(item_id)
    return SourceCandidateRead.model_validate(item)
