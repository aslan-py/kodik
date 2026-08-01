"""trim_check_constraints

Revision ID: 2c4822b9a4f8
Revises: aa57f7adc704
Create Date: 2026-07-31 16:31:26.998793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c4822b9a4f8'
down_revision: Union[str, Sequence[str], None] = 'aa57f7adc704'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Колонки, обёрнутые в StrippedString (core/database.py): TypeDecorator
# чистит пробелы только на пути через SQLAlchemy, ручной SQL (DBeaver и т.п.)
# идёт мимо него. CHECK — единственный уровень, который ловит правку
# напрямую в БД. Для NULL constraint не срабатывает (col = btrim(col) даёт
# NULL, а не false), поэтому nullable-колонки отдельно оговаривать не нужно.
_CHECKS = [
    ('competitor', 'name', 'ck_competitor_name_trimmed'),
    ('competitor', 'inn', 'ck_competitor_inn_trimmed'),
    ('source', 'name', 'ck_source_name_trimmed'),
    ('trigger', 'keyword', 'ck_trigger_keyword_trimmed'),
    ('raw_item', 'content_hash', 'ck_raw_item_content_hash_trimmed'),
    ('raw_item', 'html_file_path', 'ck_raw_item_html_file_path_trimmed'),
    (
        'raw_item',
        'source_request_url',
        'ck_raw_item_source_request_url_trimmed',
    ),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column, name in _CHECKS:
        op.create_check_constraint(
            name, table, sa.text(f'{column} = btrim({column})')
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, _column, name in reversed(_CHECKS):
        op.drop_constraint(name, table, type_='check')
