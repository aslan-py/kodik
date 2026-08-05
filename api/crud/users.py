"""Репозиторий пользователей API: регистрация, логин, список, смена роли.

Сессия — в self.session (через __init__), методы её не принимают.
Транзакцией (commit) управляет вызывающий код (роутер) — здесь только
запросы, как и в src/bp*/crud.py.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.users import UserRegister
from api.security import hash_password
from core.enums import UserRole
from src.bp3.models import Department
from src.bp5.models import User


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

    async def list_all(self) -> Sequence[User]:
        result = await self.session.execute(select(User))
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
