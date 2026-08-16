"""Пользователи в админке + вход в неё.

`UserAdmin` — модель из `ADMIN_USER_MODEL` (см. api/admin/__init__.py):
именно её `authenticate` FastAdmin зовёт на форме входа.

Кто может войти: `admin` и `analyst` — те же роли, что и `EditorDep` в API
(api/dependencies.py). `viewer`/`pending` получают отказ.

Кто может править саму таблицу `user`: **только `admin`**. Иначе `analyst`,
войдя в админку, поменял бы себе `role` на `admin` — тихая эскалация
привилегий. Смена ролей остаётся у админа (и у `PATCH /users/{id}/role`).

`password_hash` в форму не выводится (`exclude`): пароль задаётся через
штатную кнопку смены пароля, которая зовёт `change_password` — она хэширует
значение тем же `api/security.py::hash_password`, что и остальной API.
"""

from uuid import UUID

from fastadmin import WidgetType, register
from sqlalchemy import select

from api.admin.base import MENU_ADMIN_REFERENCES, KodikModelAdmin
from api.security import hash_password, verify_password
from core.database import AsyncSessionLocal
from core.enums import UserRole
from src.bp5.models import User

# Роли, которым разрешён вход в админку.
ADMIN_LOGIN_ROLES = (UserRole.admin, UserRole.analyst)


async def _get_role(user_id: UUID | int | None) -> UserRole | None:
    """Роль по id — для проверок прав внутри админки."""
    if user_id is None:
        return None
    async with AsyncSessionLocal() as session:
        user = await session.get(User, int(user_id))
        return user.role if user else None


@register(User, sqlalchemy_sessionmaker=AsyncSessionLocal)
class UserAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_REFERENCES
    verbose_name = 'Пользователь'
    verbose_name_plural = 'Список'

    list_display = (
        'id',
        'full_name',
        'email',
        'role',
        'department',
        'is_active',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'full_name': 'ФИО',
        'email': 'Email (он же логин)',
        'role': 'Роль',
        'department': 'Отдел',
        'telegram_id': 'Telegram chat_id',
        'is_active': 'Активен',
    }
    list_select_related = ('department',)
    list_filter = ('full_name', 'email', 'role', 'is_active', 'department')
    search_fields = ('full_name', 'email')
    search_help_text = 'Поиск по ФИО или email'
    ordering = ('id',)
    exclude = ('password_hash',)

    formfield_overrides = {  # noqa: RUF012
        'full_name': (
            WidgetType.Input,
            {'placeholder': 'ФИО получателя, например: Иванов Пётр'},
        ),
        'email': (
            WidgetType.EmailInput,
            {
                'placeholder': (
                    'Адрес для входа и для email-алертов, '
                    'например: ivanov@company.ru'
                )
            },
        ),
        'telegram_id': (
            WidgetType.InputNumber,
            {
                'placeholder': (
                    'Числовой chat_id для telegram-алертов (не @username), '
                    'например: 123456789. Можно не заполнять'
                )
            },
        ),
    }

    async def authenticate(
        self, username: str, password: str
    ) -> UUID | int | None:
        """Вход в админку: email + пароль, роль admin/analyst.

        `username` — это значение поля из ADMIN_USER_MODEL_USERNAME_FIELD,
        у нас `email` (он же логин в API).
        """
        async with AsyncSessionLocal() as session:
            user = await session.scalar(
                select(User).where(
                    User.email == username,
                    User.is_active.is_(True),
                    User.role.in_(ADMIN_LOGIN_ROLES),
                )
            )
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user.id

    async def change_password(
        self, id: UUID | int | str, password: str
    ) -> None:
        """Смена пароля из админки — тем же bcrypt, что и в API."""
        async with AsyncSessionLocal() as session:
            user = await session.get(User, int(id))
            if user is None:
                return
            user.password_hash = hash_password(password)
            await session.commit()

    # --- Права: таблицу пользователей правит только admin ---

    async def has_add_permission(
        self, user_id: UUID | int | None = None
    ) -> bool:
        return await _get_role(user_id) == UserRole.admin

    async def has_change_permission(
        self, user_id: UUID | int | None = None
    ) -> bool:
        return await _get_role(user_id) == UserRole.admin
