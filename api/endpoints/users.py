"""Пользователи API: GET /users/me, GET /users, PATCH /users/{id}/role.

GET /users/me доступен pending (единственный эндпоинт без require_role —
FASTAPI_PLAN.md, п.4). Список и смена роли — только analyst/admin, это и
есть механизм подтверждения pending → viewer/analyst.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.crud.users import UserCRUD
from api.dependencies import CurrentUser, SessionDep, require_role
from api.responses import (
    ME_RESPONSES,
    USER_ROLE_UPDATE_RESPONSES,
    USERS_LIST_RESPONSES,
)
from api.schemas.users import UserRead, UserRoleUpdate
from core.enums import UserRole
from src.bp5.models import User

router = APIRouter()

ApproverDep = Annotated[
    User, Depends(require_role(UserRole.analyst, UserRole.admin))
]


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
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.get(
    '',
    response_model=list[UserRead],
    responses=USERS_LIST_RESPONSES,
    summary='Список пользователей',
    description=(
        'Доступ: только `analyst` и `admin`.\n\n'
        'По этому списку видно, у кого `role=pending` — их нужно '
        'подтвердить через `PATCH /users/{id}/role`.'
    ),
)
async def list_users(
    session: SessionDep, _approver: ApproverDep
) -> list[UserRead]:
    users = await UserCRUD(session).list_all()
    return [UserRead.model_validate(u) for u in users]


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
    crud = UserCRUD(session)
    user = await crud.get_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Пользователь не найден')
    user = await crud.update_role(user, data.role)
    await session.commit()
    return UserRead.model_validate(user)
