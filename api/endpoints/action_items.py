"""План действий BP-6: POST/GET /action-items, GET/PATCH /action-items/{id}.

Тонкий слой над ActionItemService (api/service/action_items.py) — вся
бизнес-логика (видимость по отделу, разграничение правки viewer vs
analyst/admin) там. Чтение — viewer/analyst/admin (не pending). Создание
— только analyst/admin. Правка — viewer тоже может, но только
status/expected_result и только в задачах своего отдела (сервис это
проверяет и обрубает).
"""

from datetime import date

from fastapi import APIRouter, HTTPException

from api.dependencies import EditorDep, SessionDep, ViewerDep
from api.responses import (
    ACTION_ITEM_CREATE_RESPONSES,
    ACTION_ITEM_DETAIL_RESPONSES,
    ACTION_ITEM_LIST_RESPONSES,
    ACTION_ITEM_UPDATE_RESPONSES,
)
from api.schemas.action_items import (
    ActionItemCreate,
    ActionItemRead,
    ActionItemUpdate,
)
from api.service.action_items import ActionItemService
from core.enums import ActionStatus

router = APIRouter()


@router.post(
    '',
    response_model=ActionItemRead,
    status_code=201,
    responses=ACTION_ITEM_CREATE_RESPONSES,
    summary='Завести задачу плана действий',
    description=(
        'Доступ: только `analyst` и `admin`.\n\n'
        'Если передан `assigned_user_id`, он должен состоять именно в '
        '`department_id` этой задачи — иначе 409.'
    ),
)
async def create_action_item(
    data: ActionItemCreate, session: SessionDep, _editor: EditorDep
) -> ActionItemRead:
    return await ActionItemService(session).create_item(data)


@router.get(
    '',
    response_model=list[ActionItemRead],
    responses=ACTION_ITEM_LIST_RESPONSES,
    summary='Список задач плана действий',
    description=(
        'Доступ: `viewer`, `analyst`, `admin` (не `pending`).\n\n'
        '`viewer` видит только задачи СВОЕГО отдела (по '
        '`User.department_id`) — весь отдел, не только те, где он '
        '`assigned_user_id`. `department_id` в query для `viewer` '
        'игнорируется (всегда его собственный отдел) — остальные фильтры '
        'работают для всех ролей.\n\n'
        'Фильтры: `task` — подстрока без учёта регистра; '
        '`status`/`assigned_user_id`/`showcase_event_id` — точное '
        'совпадение (`showcase_event_id` удобен, чтобы проверить, есть '
        'ли уже задача по конкретному событию витрины); '
        '`deadline_from`/`deadline_to` '
        '— включительный диапазон срока; `priority` — точное '
        'совпадение с отображаемым приоритетом связанного события витрины '
        '(`П1`—`П4`). Все фильтры объединяются условием AND.'
    ),
)
async def list_action_items(
    session: SessionDep,
    viewer: ViewerDep,
    department_id: int | None = None,
    status: ActionStatus | None = None,
    task: str | None = None,
    assigned_user_id: int | None = None,
    showcase_event_id: int | None = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    priority: str | None = None,
) -> list[ActionItemRead]:
    if (
        deadline_from is not None
        and deadline_to is not None
        and deadline_from > deadline_to
    ):
        raise HTTPException(
            422, 'deadline_from не может быть позже deadline_to'
        )
    return await ActionItemService(session).list_items(
        viewer,
        department_id,
        status,
        task,
        assigned_user_id,
        showcase_event_id,
        deadline_from,
        deadline_to,
        priority,
    )


@router.get(
    '/{item_id}',
    response_model=ActionItemRead,
    responses=ACTION_ITEM_DETAIL_RESPONSES,
    summary='Задача плана действий по id',
    description=(
        'Доступ: `viewer`, `analyst`, `admin` (не `pending`).\n\n'
        '`viewer` получает 404 (не 403), если задача не его отдела — '
        'чужие задачи по id не подтверждаются.'
    ),
)
async def read_action_item(
    item_id: int, session: SessionDep, viewer: ViewerDep
) -> ActionItemRead:
    return await ActionItemService(session).get_item(viewer, item_id)


@router.patch(
    '/{item_id}',
    response_model=ActionItemRead,
    responses=ACTION_ITEM_UPDATE_RESPONSES,
    summary='Править задачу плана действий',
    description=(
        'Доступ: `viewer`, `analyst`, `admin` (не `pending`).\n\n'
        '`viewer` — только `status`/`expected_result`, и только в задаче '
        'своего отдела (остальные поля молча игнорируются, 404 если '
        'задача чужого отдела). `analyst`/`admin` — любое поле любой '
        'задачи, включая `department_id`/`assigned_user_id` (согласованность '
        'между ними проверяется — 409, если не совпадают).'
    ),
)
async def update_action_item(
    item_id: int,
    data: ActionItemUpdate,
    session: SessionDep,
    viewer: ViewerDep,
) -> ActionItemRead:
    return await ActionItemService(session).update_item(viewer, item_id, data)
