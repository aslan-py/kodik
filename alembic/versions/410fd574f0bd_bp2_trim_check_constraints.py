"""bp2_trim_check_constraints

Revision ID: 410fd574f0bd
Revises: 2c4822b9a4f8
Create Date: 2026-07-31 16:39:29.744618

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '410fd574f0bd'
down_revision: Union[str, Sequence[str], None] = '2c4822b9a4f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Те же грабли, что в bp1: StrippedString (core/database.py) чистит пробелы
# только на пути через SQLAlchemy, ручной SQL (DBeaver) идёт мимо него.
# CHECK — единственный уровень, ловящий правку напрямую в БД.
_CHECKS = [
    ('region', 'name_display', 'ck_region_name_display_trimmed'),
    ('region', 'macro_region', 'ck_region_macro_region_trimmed'),
    ('black_domain', 'domain', 'ck_black_domain_domain_trimmed'),
    ('black_domain', 'reason', 'ck_black_domain_reason_trimmed'),
    ('stop_word', 'phrase', 'ck_stop_word_phrase_trimmed'),
    ('stop_word', 'note', 'ck_stop_word_note_trimmed'),
    ('topic_limit', 'note', 'ck_topic_limit_note_trimmed'),
    ('normalized_item', 'title', 'ck_normalized_item_title_trimmed'),
    (
        'normalized_item',
        'media_name',
        'ck_normalized_item_media_name_trimmed',
    ),
    (
        'normalized_item',
        'media_domain',
        'ck_normalized_item_media_domain_trimmed',
    ),
    ('normalized_item', 'url', 'ck_normalized_item_url_trimmed'),
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
