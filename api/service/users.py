"""Бизнес-логика пользователей: профиль, список, смена роли, правка себя.

Роутер (api/endpoints/users.py) только вызывает методы UserService — вся
логика (проверки конфликтов, HTTPException, commit) живёт здесь.
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.users import UserCRUD
from api.schemas.users import UserAdminUpdate, UserRead, UserUpdateMe
from api.security import verify_password
from src.bp5.models import User

_WRONG_CURRENT_PASSWORD = HTTPException(
    status.HTTP_401_UNAUTHORIZED, 'Неверный текущий пароль'
)


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = UserCRUD(session)

    async def get_me(self, user: User) -> UserRead:
        return UserRead.model_validate(user)

    async def list_users(
        self,
        full_name: str | None = None,
        email: str | None = None,
        department_id: int | None = None,
    ) -> list[UserRead]:
        users = await self.crud.list_all(full_name, email, department_id)
        return [UserRead.model_validate(u) for u in users]

    async def get_by_id(self, user_id: int) -> UserRead:
        user = await self.crud.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, 'Пользователь не найден'
            )
        return UserRead.model_validate(user)

    async def update_admin(
        self, user_id: int, data: UserAdminUpdate
    ) -> UserRead:
        user = await self.crud.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, 'Пользователь не найден'
            )
        changes = data.model_dump(exclude_unset=True)
        if 'department_id' in changes and changes['department_id'] is not None:
            if not await self.crud.department_exists(changes['department_id']):
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    f'Отдел с id={changes["department_id"]} не найден',
                )
        user = await self.crud.update_admin(user, changes)
        await self.session.commit()
        return UserRead.model_validate(user)

    async def update_me(self, user: User, data: UserUpdateMe) -> UserRead:
        """Правка своих данных. current_password обязателен, только если
        меняется email или password — защита от угона токена/сессии.
        role в UserUpdateMe нет вообще (extra='forbid' на схеме), так что
        self-service повышение прав через этот эндпоинт невозможно."""
        changes = data.model_dump(
            exclude_unset=True, exclude={'current_password'}
        )
        if not changes:
            return UserRead.model_validate(user)

        if 'email' in changes or 'password' in changes:
            if data.current_password is None or not verify_password(
                data.current_password, user.password_hash
            ):
                raise _WRONG_CURRENT_PASSWORD

        if 'email' in changes:
            existing = await self.crud.get_by_email(changes['email'])
            if existing is not None and existing.id != user.id:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    'Этот email уже занят другим пользователем',
                )

        if changes.get('telegram_id') is not None:
            existing = await self.crud.get_by_telegram_id(
                changes['telegram_id']
            )
            if existing is not None and existing.id != user.id:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    'Этот telegram_id уже привязан к другому пользователю',
                )

        if changes.get('department_id') is not None:
            if not await self.crud.department_exists(changes['department_id']):
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    f'Отдел с id={changes["department_id"]} не найден',
                )

        user = await self.crud.update_self(user, changes)
        await self.session.commit()
        return UserRead.model_validate(user)
