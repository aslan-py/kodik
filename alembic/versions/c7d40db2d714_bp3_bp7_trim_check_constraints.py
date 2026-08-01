"""bp3_bp7_trim_check_constraints

Revision ID: c7d40db2d714
Revises: 410fd574f0bd
Create Date: 2026-07-31 18:41:06.634496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d40db2d714'
down_revision: Union[str, Sequence[str], None] = '410fd574f0bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Тот же приём, что в bp1/bp2: StrippedString (core/database.py) чистит
# пробелы только на пути через SQLAlchemy, ручной SQL (DBeaver) идёт мимо
# него. CHECK — единственный уровень, ловящий правку напрямую в БД.
_CHECKS = [
    ('category', 'name', 'ck_category_name_trimmed'),
    ('category', 'note', 'ck_category_note_trimmed'),
    ('department', 'name', 'ck_department_name_trimmed'),
    ('department', 'note', 'ck_department_note_trimmed'),
    ('categorized_event', 'action', 'ck_categorized_event_action_trimmed'),
    ('categorized_event', 'comment', 'ck_categorized_event_comment_trimmed'),
    (
        'categorized_event',
        'llm_model',
        'ck_categorized_event_llm_model_trimmed',
    ),
    (
        'categorized_event',
        'prompt_version',
        'ck_categorized_event_prompt_version_trimmed',
    ),
    ('showcase_event', 'title', 'ck_showcase_event_title_trimmed'),
    ('showcase_event', 'media', 'ck_showcase_event_media_trimmed'),
    ('showcase_event', 'region', 'ck_showcase_event_region_trimmed'),
    (
        'showcase_event',
        'macro_region',
        'ck_showcase_event_macro_region_trimmed',
    ),
    ('showcase_event', 'competitor', 'ck_showcase_event_competitor_trimmed'),
    ('showcase_event', 'source_url', 'ck_showcase_event_source_url_trimmed'),
    ('showcase_event', 'priority', 'ck_showcase_event_priority_trimmed'),
    ('showcase_event', 'category', 'ck_showcase_event_category_trimmed'),
    ('showcase_event', 'tonality', 'ck_showcase_event_tonality_trimmed'),
    ('showcase_event', 'action', 'ck_showcase_event_action_trimmed'),
    ('showcase_event', 'department', 'ck_showcase_event_department_trimmed'),
    ('event_type', 'name', 'ck_event_type_name_trimmed'),
    ('channel', 'name', 'ck_channel_name_trimmed'),
    ('user', 'full_name', 'ck_user_full_name_trimmed'),
    ('user', 'email', 'ck_user_email_trimmed'),
    ('action_item', 'task', 'ck_action_item_task_trimmed'),
    ('source_candidate', 'domain', 'ck_source_candidate_domain_trimmed'),
    (
        'source_candidate',
        'evidence_url',
        'ck_source_candidate_evidence_url_trimmed',
    ),
    (
        'source_candidate',
        'moderated_by',
        'ck_source_candidate_moderated_by_trimmed',
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
