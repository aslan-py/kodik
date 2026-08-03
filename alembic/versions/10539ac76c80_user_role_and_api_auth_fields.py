"""user_role_and_api_auth_fields

Revision ID: 10539ac76c80
Revises: 2c68ffa6ee8b
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

import core.database  # noqa: F401 — для типа StrippedString

# revision identifiers, used by Alembic.
revision: str = '10539ac76c80'
down_revision: Union[str, Sequence[str], None] = '2c68ffa6ee8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role_enum = postgresql.ENUM(
    'pending', 'viewer', 'analyst', 'admin', name='user_role'
)


def upgrade() -> None:
    """Upgrade schema."""
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # password_hash — NOT NULL без дефолта в модели, но у существующих строк
    # значения ещё нет. Добавляем с временным server_default, сразу снимаем,
    # чтобы дальнейшие INSERT (в обход API) не проходили без явного хэша.
    op.add_column(
        'user',
        sa.Column(
            'password_hash',
            core.database.StrippedString(length=256),
            server_default='',
            nullable=False,
            comment='bcrypt-хэш пароля для логина в API',
        ),
    )
    op.alter_column('user', 'password_hash', server_default=None)

    op.add_column(
        'user',
        sa.Column(
            'role',
            user_role_enum,
            server_default=sa.text("'pending'"),
            nullable=False,
            comment=(
                'Уровень доступа к API (не отдел): '
                'pending/viewer/analyst/admin'
            ),
        ),
    )

    op.alter_column(
        'user',
        'telegram_id',
        existing_type=sa.BigInteger(),
        nullable=True,
        existing_comment=(
            'Числовой chat_id для канала telegram (sendMessage требует '
            'id, не @username)'
        ),
        comment=(
            'Числовой chat_id для канала telegram (sendMessage требует '
            'id, не @username). NULL, пока пользователь не привязал telegram'
        ),
    )
    op.alter_column(
        'user',
        'email',
        existing_type=core.database.StrippedString(length=256),
        existing_comment='Адрес для канала email',
        comment='Адрес для канала email, он же логин API',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'user',
        'email',
        existing_type=core.database.StrippedString(length=256),
        existing_comment='Адрес для канала email, он же логин API',
        comment='Адрес для канала email',
    )
    op.alter_column(
        'user',
        'telegram_id',
        existing_type=sa.BigInteger(),
        nullable=False,
        existing_comment=(
            'Числовой chat_id для канала telegram (sendMessage требует '
            'id, не @username). NULL, пока пользователь не привязал telegram'
        ),
        comment=(
            'Числовой chat_id для канала telegram (sendMessage требует '
            'id, не @username)'
        ),
    )
    op.drop_column('user', 'role')
    op.drop_column('user', 'password_hash')

    user_role_enum.drop(op.get_bind(), checkfirst=True)
