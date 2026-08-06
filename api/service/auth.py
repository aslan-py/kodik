"""Бизнес-логика аутентификации: регистрация, логин, logout, сброс пароля.

Роутер (api/endpoints/auth.py) только вызывает методы AuthService — вся
логика (проверки конфликтов, HTTPException, commit) живёт здесь, а не в
эндпоинте.
"""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.crud.users import UserCRUD
from api.schemas.users import (
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
    UserLogin,
    UserRead,
    UserRegister,
)
from api.security import (
    create_access_token,
    generate_reset_code,
    hash_password,
    verify_password,
)
from core.config import settings
from core.mail import send_email
from src.bp5.models import User

logger = logging.getLogger(__name__)

_RESET_REQUESTED_MESSAGE = MessageResponse(
    detail=(
        'Если такой email зарегистрирован, код для сброса пароля '
        'отправлен на почту'
    )
)
_INVALID_RESET_CODE = HTTPException(
    status.HTTP_400_BAD_REQUEST, 'Неверный или истёкший код'
)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = UserCRUD(session)

    async def register(self, data: UserRegister) -> UserRead:
        """Self-service регистрация. role всегда pending — без доступа до
        подтверждения analyst/admin (детали — FASTAPI_PLAN.md, п.4)."""
        if await self.crud.get_by_email(data.email) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                'Пользователь с таким email уже существует',
            )
        if (
            data.telegram_id is not None
            and await self.crud.get_by_telegram_id(data.telegram_id) is not None
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                'Этот telegram_id уже привязан к другому пользователю',
            )
        if (
            data.department_id is not None
            and not await self.crud.department_exists(data.department_id)
        ):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f'Отдел с id={data.department_id} не найден',
            )
        user = await self.crud.create(data)
        await self.session.commit()
        return UserRead.model_validate(user)

    async def login(self, data: UserLogin) -> Token:
        user = await self.crud.get_by_email(data.email)
        if user is None or not verify_password(
            data.password, user.password_hash
        ):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, 'Неверный email или пароль'
            )
        return Token(access_token=create_access_token(subject=str(user.id)))

    async def logout(self, user: User) -> MessageResponse:
        """Stateless no-op: JWT не хранит состояние на сервере, отзыва
        токена и refresh-токенов в проекте нет (осознанное решение —
        см. plan-файл). Токен технически остаётся валиден до истечения
        jwt_expire_minutes — реальный выход обеспечивает клиент, удаляя
        токен у себя."""
        return MessageResponse(
            detail=f'Пользователь {user.email} вышел из системы'
        )

    async def request_password_reset(
        self, data: PasswordResetRequest
    ) -> MessageResponse:
        """Всегда один и тот же generic-ответ — не палим существование
        email в системе (защита от enumeration)."""
        user = await self.crud.get_by_email(data.email)
        if user is not None:
            code = generate_reset_code()
            await self.crud.create_reset_code(user.id, hash_password(code))
            await self.session.commit()
            try:
                await send_email(
                    to=user.email,
                    subject='Код для сброса пароля',
                    body=(
                        f'Ваш код для сброса пароля: {code}\n'
                        'Действует '
                        f'{settings.password_reset_code_expire_minutes} '
                        'минут. Если вы не запрашивали сброс пароля, '
                        'проигнорируйте это письмо.'
                    ),
                )
            except Exception:
                logger.exception(
                    'Не удалось отправить письмо сброса пароля user_id=%s',
                    user.id,
                )
        return _RESET_REQUESTED_MESSAGE

    async def confirm_password_reset(
        self, data: PasswordResetConfirm
    ) -> MessageResponse:
        user = await self.crud.get_by_email(data.email)
        code_row = (
            await self.crud.get_active_reset_code(user.id) if user else None
        )
        if code_row is None or code_row.expires_at < datetime.now(UTC):
            raise _INVALID_RESET_CODE
        if not verify_password(data.code, code_row.code_hash):
            await self.crud.register_failed_attempt(code_row)
            raise _INVALID_RESET_CODE

        await self.crud.update_password(user, data.new_password)
        await self.crud.mark_code_used(code_row)
        await self.session.commit()
        return MessageResponse(detail='Пароль успешно изменён')
