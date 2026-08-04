"""FastAPI-обвязка над core.database + авторизация запроса.

SessionDep — перенесён сюда из core/database.py (см. FASTAPI_PLAN.md, п.1):
core.database остаётся framework-agnostic, Depends живёт только здесь.
get_current_user — декодирует JWT, читает User по sub. require_role(...) —
фабрика зависимостей для проверки role на конкретном роутере: ролей всего
4 (core.enums.UserRole), отдельная библиотека прав не нужна.

ViewerDep/EditorDep/ApproverDep — готовые Annotated-алиасы под конкретные
пороги доступа, переиспользуемые в api/endpoints/*.py. Собраны в одном
месте (а не объявлены по одному в каждом файле эндпоинтов), чтобы вся
матрица доступа была видна сразу, без открытия каждого роутера.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.users import UserCRUD
from api.security import bearer_scheme, decode_access_token
from core.database import get_async_session
from core.enums import UserRole
from src.bp5.models import User

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Не удалось подтвердить учётные данные',
    headers={'WWW-Authenticate': 'Bearer'},
)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: SessionDep,
) -> User:
    if credentials is None:
        raise _CREDENTIALS_ERROR

    payload = decode_access_token(credentials.credentials)
    if payload is None or 'sub' not in payload:
        raise _CREDENTIALS_ERROR

    user = await UserCRUD(session).get_by_id(int(payload['sub']))
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole) -> Callable[[User], User]:
    """Зависимость: 403, если роль пользователя не входит в allowed."""

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав для этого действия',
            )
        return user

    return checker


# Чтение витрины и т.п. — viewer/analyst/admin (не pending).
ViewerDep = Annotated[
    User,
    Depends(require_role(UserRole.viewer, UserRole.analyst, UserRole.admin)),
]
# Правка витрины и т.п. — только analyst/admin.
EditorDep = Annotated[
    User, Depends(require_role(UserRole.analyst, UserRole.admin))
]
# Подтверждение pending -> роль, смена роли — только analyst/admin.
ApproverDep = Annotated[
    User, Depends(require_role(UserRole.analyst, UserRole.admin))
]
