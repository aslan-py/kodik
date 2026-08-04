"""Пользователи API: GET/PATCH /users/me, GET /users, PATCH /users/{id}/role.

Тонкий слой над UserService (api/service/users.py) — вся бизнес-логика
там. GET /users/me доступен pending (единственный эндпоинт без require_role
— FASTAPI_PLAN.md, п.4). Список и смена роли — только analyst/admin, это и
есть механизм подтверждения pending → viewer/analyst.
"""

from fastapi import APIRouter

from api.dependencies import ApproverDep, CurrentUser, SessionDep
from api.responses import (
    ME_RESPONSES,
    ME_UPDATE_RESPONSES,
    USER_ROLE_UPDATE_RESPONSES,
    USERS_LIST_RESPONSES,
)
from api.schemas.users import UserRead, UserRoleUpdate, UserUpdateMe
from api.service.users import UserService

router = APIRouter()


@router.get(
    '/me',
    response_model=UserRead,
    responses=ME_RESPONSES,
    summary='Профиль текущего пользователя',
    description=(
        'Доступ: любая роль, включая `pending` — единственный эндпоинт, '
        'доступный сразу после регистрации, до подтверждения роли.'
    ),
)
async def read_me(user: CurrentUser, session: SessionDep) -> UserRead:
    return await UserService(session).get_me(user)


@router.patch(
    '/me',
    response_model=UserRead,
    responses=ME_UPDATE_RESPONSES,
    summary='Править свои данные',
    description=(
        'Доступ: любая роль, включая `pending`.\n\n'
        'Правит `email`, `password`, `full_name`, `department_id`, '
        '`telegram_id` — все поля опциональны (partial update). `role` '
        'через этот эндпоинт изменить нельзя (её нет в схеме, лишнее поле '
        'даёт 422).\n\n'
        'Если меняется `email` или `password` — обязателен '
        '`current_password`, иначе 401 (защита от смены логина/пароля '
        'украденным токеном).'
    ),
)
async def update_me(
    data: UserUpdateMe, user: CurrentUser, session: SessionDep
) -> UserRead:
    return await UserService(session).update_me(user, data)


@router.get(
    '',
    response_model=list[UserRead],
    responses=USERS_LIST_RESPONSES,
    summary='Список пользователей',
    description=(
        'Доступ: только `analyst` и `admin`.\n\n'
        'По этому списку видно, у кого `role=pending` — их нужно '
        'подтвердить через `PATCH /users/{id}/role`.\n\n'
        'Фильтры (можно комбинировать): `full_name`/`email` — подстрока '
        'без учёта регистра, `department_id` — точное совпадение.'
    ),
)
async def list_users(
    session: SessionDep,
    _approver: ApproverDep,
    full_name: str | None = None,
    email: str | None = None,
    department_id: int | None = None,
) -> list[UserRead]:
    return await UserService(session).list_users(
        full_name, email, department_id
    )


@router.patch(
    '/{user_id}/role',
    response_model=UserRead,
    responses=USER_ROLE_UPDATE_RESPONSES,
    summary='Сменить роль пользователя',
    description=(
        'Доступ: только `analyst` и `admin`.\n\n'
        'Единственный способ подтвердить `pending` → `viewer`/`analyst` '
        'или назначить `admin` — правки роли себе самому эндпоинт не '
        'запрещает отдельно, но обычно это делает другой admin/analyst.'
    ),
)
async def update_role(
    user_id: int,
    data: UserRoleUpdate,
    session: SessionDep,
    _approver: ApproverDep,
) -> UserRead:
    return await UserService(session).update_role(user_id, data)
