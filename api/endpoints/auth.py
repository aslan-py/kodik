"""Аутентификация: регистрация, логин, logout, сброс пароля.

Тонкий слой над AuthService (api/service/auth.py) — вся бизнес-логика
там, эндпоинты только парсят запрос и вызывают сервис.
"""

from fastapi import APIRouter, status

from api.dependencies import CurrentUser, SessionDep
from api.responses import (
    LOGIN_RESPONSES,
    LOGOUT_RESPONSES,
    PASSWORD_RESET_CONFIRM_RESPONSES,
    REGISTER_RESPONSES,
)
from api.schemas.users import (
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
    UserLogin,
    UserRead,
    UserRegister,
)
from api.service.auth import AuthService

router = APIRouter()


@router.post(
    '/register',
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses=REGISTER_RESPONSES,
    summary='Регистрация нового пользователя',
    description=(
        'Доступ: публично, токен не нужен.\n\n'
        'Создаёт пользователя с ролью `pending` — доступа нет ни к одному '
        'эндпоинту, кроме `GET /users/me`. До `viewer`/`analyst`/`admin` '
        'роль поднимает `analyst` или `admin` через '
        '`PATCH /users/{id}/role`.\n\n'
        '`telegram_id` необязателен: без него пользователь работает в '
        'системе, но алерты BP-5 идут только на email.'
    ),
)
async def register(data: UserRegister, session: SessionDep) -> UserRead:
    return await AuthService(session).register(data)


@router.post(
    '/login',
    response_model=Token,
    responses=LOGIN_RESPONSES,
    summary='Логин, выдача JWT',
    description=(
        'Доступ: публично, токен не нужен.\n\n'
        'Проверяет email и пароль, возвращает `access_token` (JWT, '
        'Bearer). Полученный токен — в заголовок '
        '`Authorization: Bearer <token>` для всех остальных запросов '
        '(или в поле Value кнопки Authorize в Swagger).'
    ),
)
async def login(data: UserLogin, session: SessionDep) -> Token:
    return await AuthService(session).login(data)


@router.post(
    '/logout',
    response_model=MessageResponse,
    responses=LOGOUT_RESPONSES,
    summary='Выход из профиля',
    description=(
        'Доступ: любая роль, включая `pending` — нужен только валидный '
        'токен.\n\n'
        'JWT в проекте stateless: отзыва токена и refresh-токенов нет. '
        'Эндпоинт ничего не хранит на сервере — реальный выход '
        'обеспечивает клиент, удаляя токен у себя. До истечения '
        '`jwt_expire_minutes` токен технически остаётся валиден, если '
        'кто-то успел его скопировать до выхода.'
    ),
)
async def logout(user: CurrentUser, session: SessionDep) -> MessageResponse:
    return await AuthService(session).logout(user)


@router.post(
    '/password-reset/request',
    response_model=MessageResponse,
    summary='Запросить код сброса пароля',
    description=(
        'Доступ: публично, токен не нужен.\n\n'
        'Всегда возвращает один и тот же ответ независимо от того, найден '
        'ли такой email — так email пользователей нельзя перебрать через '
        'этот эндпоинт. Если email существует, на него уходит письмо с '
        '6-значным кодом (`password_reset_code_expire_minutes` минут '
        'жизни, максимум 5 попыток ввода).'
    ),
)
async def request_password_reset(
    data: PasswordResetRequest, session: SessionDep
) -> MessageResponse:
    return await AuthService(session).request_password_reset(data)


@router.post(
    '/password-reset/confirm',
    response_model=MessageResponse,
    responses=PASSWORD_RESET_CONFIRM_RESPONSES,
    summary='Подтвердить сброс пароля кодом из письма',
    description=(
        'Доступ: публично, токен не нужен.\n\n'
        'Код одноразовый, действует ограниченное время и максимум 5 '
        'попыток ввода — после этого нужно запросить новый через '
        '`POST /auth/password-reset/request`.'
    ),
)
async def confirm_password_reset(
    data: PasswordResetConfirm, session: SessionDep
) -> MessageResponse:
    return await AuthService(session).confirm_password_reset(data)
