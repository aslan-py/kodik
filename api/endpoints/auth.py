"""Регистрация и логин: POST /auth/register, POST /auth/login."""

from fastapi import APIRouter, HTTPException, status

from api.crud.users import UserCRUD
from api.dependencies import SessionDep
from api.responses import LOGIN_RESPONSES, REGISTER_RESPONSES
from api.schemas.users import Token, UserLogin, UserRead, UserRegister
from api.security import create_access_token, verify_password

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
    """Self-service регистрация. role всегда pending — без доступа до
    подтверждения analyst/admin (детали — FASTAPI_PLAN.md, п.4)."""
    crud = UserCRUD(session)
    if await crud.get_by_email(data.email) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            'Пользователь с таким email уже существует',
        )
    if (
        data.telegram_id is not None
        and await crud.get_by_telegram_id(data.telegram_id) is not None
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            'Этот telegram_id уже привязан к другому пользователю',
        )
    if data.department_id is not None and not await crud.department_exists(
        data.department_id
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f'Отдел с id={data.department_id} не найден',
        )
    user = await crud.create(data)
    await session.commit()
    return UserRead.model_validate(user)


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
    user = await UserCRUD(session).get_by_email(data.email)
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, 'Неверный email или пароль'
        )
    return Token(access_token=create_access_token(subject=str(user.id)))
