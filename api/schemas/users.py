"""Pydantic-схемы регистрации/логина/чтения пользователя API."""

from pydantic import BaseModel, ConfigDict, EmailStr

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


class UserRoleUpdate(BaseModel):
    """Тело PATCH /users/{id}/role — только admin/analyst подтверждают роль."""

    role: UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'
