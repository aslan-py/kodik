"""seed default admin user

Revision ID: d2fcfdb80aa9
Revises: d8be5a20d9b1
Create Date: 2026-08-10 22:18:57.030672

Данные заводятся здесь, а НЕ в core/scripts/stages/dictionaries.py (обычное
место для справочных/демо-данных проекта) — намеренное исключение: наличие
администратора должно гарантироваться самим `alembic upgrade head`, а не
опциональным сидер-скриптом, который на новой среде легко забыть запустить
(см. openspec/changes/seed-admin-user-migration/design.md, Decisions).

Пароль 'Admin123' — бутстрап-значение, ХРАНИТСЯ В ОТКРЫТОМ ВИДЕ В ЭТОМ ФАЙЛЕ.
Осознанный компромисс для локальной/предпром среды (см. design.md, Risks) —
сменить через /admin сразу после первого входа на любой среде, где к
репозиторию есть посторонний доступ.

ON CONFLICT (email) DO NOTHING — если admin@admin.ru уже заведён вручную
(с любым паролем/ролью), эта миграция его не трогает.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from api.security import hash_password

# revision identifiers, used by Alembic.
revision: str = 'd2fcfdb80aa9'
down_revision: Union[str, Sequence[str], None] = 'd8be5a20d9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_EMAIL = 'admin@admin.ru'
ADMIN_PASSWORD = 'Admin123'


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            'INSERT INTO "user" '
            '(full_name, email, role, password_hash, is_active) '
            "VALUES (:full_name, :email, 'admin', :password_hash, true) "
            'ON CONFLICT (email) DO NOTHING'
        ).bindparams(
            full_name='Admin',
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text('DELETE FROM "user" WHERE email = :email').bindparams(
            email=ADMIN_EMAIL
        )
    )
