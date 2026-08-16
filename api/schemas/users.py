"""Pydantic-схемы регистрации/логина/чтения пользователя API."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.validators.users import CustomPassword
from core.enums import UserRole


class UserRegister(BaseModel):
    """Тело POST /auth/register. role не принимаем — всегда pending.

    telegram_id опционален: неизвестен на момент self-service регистрации
    по email, если пользователь его не указал. Без него пользователь
    работает в системе и получает алерты только на email — до тех пор,
    пока сам не привяжет telegram_id (см. src/bp5/models.py::User).
    """

    email: EmailStr
    password: CustomPassword
    full_name: str | None = None
    department_id: int | None = None
    telegram_id: int | None = None


class UserLogin(BaseModel):
    """Тело POST /auth/login."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    department_id: int | None
    telegram_id: int | None
    role: UserRole
    is_active: bool


class UserAdminUpdate(BaseModel):
    """Частичная административная правка пользователя."""

    role: UserRole | None = None
    department_id: int | None = None
    is_active: bool | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class MessageResponse(BaseModel):
    """Generic-подтверждение для эндпоинтов без содержательного тела."""

    detail: str


class PasswordResetRequest(BaseModel):
    """Тело POST /auth/password-reset/request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Тело POST /auth/password-reset/confirm."""

    email: EmailStr
    code: str = Field(pattern=r'^\d{6}$')
    new_password: CustomPassword


class UserUpdateMe(BaseModel):
    """Тело PATCH /users/me — правка своих данных, без role/is_active.

    extra='forbid': поле вроде `role` в теле запроса даёт 422, а не тихий
    игнор — попыткаself-service повысить себе права видна сразу.
    current_password обязателен, только если меняется email или password
    (см. api/service/users.py::UserService.update_me).
    """

    model_config = ConfigDict(extra='forbid')

    email: EmailStr | None = None
    password: CustomPassword | None = None
    full_name: str | None = None
    department_id: int | None = None
    telegram_id: int | None = None
    current_password: str | None = None
