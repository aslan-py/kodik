"""Витрина BP-4: GET /showcase, GET /showcase/{id}, PATCH /showcase/{id}.

Чтение — viewer/analyst/admin (не pending). Правка — только analyst/admin.
ShowcaseCRUD.update() сама решает write-through в categorized_event +
зеркалирование в showcase_event (FASTAPI_PLAN.md, п.3) — роутер её просто
вызывает.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.crud.showcase import ShowcaseCRUD
from api.dependencies import SessionDep, require_role
from api.responses import SHOWCASE_DETAIL_RESPONSES, SHOWCASE_LIST_RESPONSES
from api.schemas.showcase import ShowcaseEventRead, ShowcaseEventUpdate
from core.enums import UserRole
from src.bp5.models import User

router = APIRouter()

ViewerDep = Annotated[
    User,
    Depends(require_role(UserRole.viewer, UserRole.analyst, UserRole.admin)),
]
EditorDep = Annotated[
    User, Depends(require_role(UserRole.analyst, UserRole.admin))
]


@router.get(
    '',
    response_model=list[ShowcaseEventRead],
    responses=SHOWCASE_LIST_RESPONSES,
    summary='Список событий витрины',
    description=(
        'Доступ: `viewer`, `analyst`, `admin` (не `pending`).\n\n'
        'Пагинация — `limit`/`offset`, сортировка по `published_at` '
        '(новые сверху).'
    ),
)
async def list_showcase(
    session: SessionDep,
    _viewer: ViewerDep,
    limit: int = 100,
    offset: int = 0,
) -> list[ShowcaseEventRead]:
    events = await ShowcaseCRUD(session).list_all(limit=limit, offset=offset)
    return [ShowcaseEventRead.model_validate(e) for e in events]


@router.get(
    '/{showcase_id}',
    response_model=ShowcaseEventRead,
    responses=SHOWCASE_DETAIL_RESPONSES,
    summary='Событие витрины по id',
    description='Доступ: `viewer`, `analyst`, `admin` (не `pending`).',
)
async def read_showcase(
    showcase_id: int, session: SessionDep, _viewer: ViewerDep
) -> ShowcaseEventRead:
    event = await ShowcaseCRUD(session).get(showcase_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Событие не найдено')
    return ShowcaseEventRead.model_validate(event)


@router.patch(
    '/{showcase_id}',
    response_model=ShowcaseEventRead,
    responses=SHOWCASE_DETAIL_RESPONSES,
    summary='Править разметку события витрины',
    description=(
        'Доступ: только `analyst` и `admin`.\n\n'
        'Правит только разметку: `priority`, `category_id`, `tonality`, '
        '`action`, `deadline`, `department_id`, `comment` — все поля '
        'опциональны (partial update), но тело не может быть пустым. '
        'Факты (`title`, `media`, `region`, `competitor`, `source_url`, '
        'координаты) через этот эндпоинт не редактируются.\n\n'
        'Пишет в `categorized_event` (источник правды) и тем же значением '
        'зеркалит `showcase_event`, чтобы оба слоя оставались в '
        'консистентном состоянии.'
    ),
)
async def update_showcase(
    showcase_id: int,
    data: ShowcaseEventUpdate,
    session: SessionDep,
    _editor: EditorDep,
) -> ShowcaseEventRead:
    event = await ShowcaseCRUD(session).update(showcase_id, data)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Событие не найдено')
    await session.commit()
    return ShowcaseEventRead.model_validate(event)
