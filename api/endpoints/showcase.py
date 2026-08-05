"""Витрина BP-4: GET /showcase, GET /showcase/{id}, PATCH /showcase/{id}.

Тонкий слой над ShowcaseService (api/service/showcase.py) — вся
бизнес-логика (write-through правка в categorized_event + зеркалирование
в showcase_event, FASTAPI_PLAN.md, п.3) там, не в эндпоинте. Чтение —
viewer/analyst/admin (не pending). Правка — только analyst/admin.
"""

from datetime import date

from fastapi import APIRouter

from api.dependencies import EditorDep, SessionDep, ViewerDep
from api.responses import SHOWCASE_DETAIL_RESPONSES, SHOWCASE_LIST_RESPONSES
from api.schemas.showcase import ShowcaseEventRead, ShowcaseEventUpdate
from api.service.showcase import ShowcaseService

router = APIRouter()


@router.get(
    '',
    response_model=list[ShowcaseEventRead],
    responses=SHOWCASE_LIST_RESPONSES,
    summary='Список событий витрины',
    description=(
        'Доступ: `viewer`, `analyst`, `admin` (не `pending`).\n\n'
        'Пагинация — `limit`/`offset`, сортировка по `published_at` '
        '(новые сверху).\n\n'
        'Фильтры (можно комбинировать): `title`/`region`/`competitor` — '
        'подстрока без учёта регистра; `category`/`priority`/`department` '
        '— точное совпадение с готовой подписью витрины (например, '
        '`priority=П1`); `published_from`/`published_to` — диапазон дат '
        '(включительно). Нужны, чтобы найти конкретное событие и его '
        '`id` для `POST /action-items`, не листая всю витрину.'
    ),
)
async def list_showcase(
    session: SessionDep,
    _viewer: ViewerDep,
    limit: int = 100,
    offset: int = 0,
    title: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    region: str | None = None,
    competitor: str | None = None,
    department: str | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
) -> list[ShowcaseEventRead]:
    return await ShowcaseService(session).list_events(
        limit=limit,
        offset=offset,
        title=title,
        category=category,
        priority=priority,
        region=region,
        competitor=competitor,
        department=department,
        published_from=published_from,
        published_to=published_to,
    )


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
    return await ShowcaseService(session).get_event(showcase_id)


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
    return await ShowcaseService(session).update_event(showcase_id, data)
