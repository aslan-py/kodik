"""Репозиторий пользователей API: регистрация, логин, список, смена роли,
правка своих данных, коды сброса пароля.

Сессия — в self.session (через __init__), методы её не принимают.
Транзакцией (commit) управляет вызывающий код (сервис из api/service/*,
см. api/service/auth.py и api/service/users.py) — здесь только запросы
и flush, как и в src/bp*/crud.py.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.users import UserRegister
from api.security import hash_password
from core.config import settings
from core.enums import UserRole
from src.bp3.models import Department
from src.bp5.models import PasswordResetCode, User

MAX_RESET_ATTEMPTS = 5


class UserCRUD:
    """Репозиторий User: доступ по email/id, регистрация, смена роли."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def department_exists(self, department_id: int) -> bool:
        return await self.session.get(Department, department_id) is not None

    async def list_all(
        self,
        full_name: str | None = None,
        email: str | None = None,
        department_id: int | None = None,
    ) -> Sequence[User]:
        """Список пользователей с опциональными фильтрами (все — AND).

        full_name/email — подстрока без учёта регистра (ilike), не
        требует точного совпадения. department_id — точное совпадение.
        """
        stmt = select(User)
        if full_name is not None:
            stmt = stmt.where(User.full_name.ilike(f'%{full_name}%'))
        if email is not None:
            stmt = stmt.where(User.email.ilike(f'%{email}%'))
        if department_id is not None:
            stmt = stmt.where(User.department_id == department_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, data: UserRegister) -> User:
        """Регистрация. role всегда pending — без доступа до подтверждения."""
        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            department_id=data.department_id,
            telegram_id=data.telegram_id,
            role=UserRole.pending,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_role(self, user: User, role: UserRole) -> User:
        user.role = role
        await self.session.flush()
        return user

    async def update_password(self, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        await self.session.flush()
        return user

    async def update_self(self, user: User, data: dict) -> User:
        """Правка своих данных. `data` — уже отфильтрованный
        exclude_unset-словарь из UserUpdateMe (без current_password),
        см. api/service/users.py::UserService.update_me."""
        for field, value in data.items():
            if field == 'password':
                user.password_hash = hash_password(value)
            else:
                setattr(user, field, value)
        await self.session.flush()
        return user

    async def create_reset_code(
        self, user_id: int, code_hash: str
    ) -> PasswordResetCode:
        """Один активный код на пользователя: старые неиспользованные
        коды удаляются перед вставкой нового."""
        await self.session.execute(
            delete(PasswordResetCode).where(
                PasswordResetCode.user_id == user_id
            )
        )
        reset_code = PasswordResetCode(
            user_id=user_id,
            code_hash=code_hash,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.password_reset_code_expire_minutes),
        )
        self.session.add(reset_code)
        await self.session.flush()
        return reset_code

    async def get_active_reset_code(
        self, user_id: int
    ) -> PasswordResetCode | None:
        stmt = select(PasswordResetCode).where(
            PasswordResetCode.user_id == user_id,
            PasswordResetCode.used_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def register_failed_attempt(
        self, code_row: PasswordResetCode
    ) -> None:
        code_row.attempts += 1
        if code_row.attempts >= MAX_RESET_ATTEMPTS:
            code_row.used_at = datetime.now(UTC)
        await self.session.flush()

    async def mark_code_used(self, code_row: PasswordResetCode) -> None:
        code_row.used_at = datetime.now(UTC)
        await self.session.flush()
