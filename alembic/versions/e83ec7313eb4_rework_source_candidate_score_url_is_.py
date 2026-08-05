"""rework source_candidate score url is_active status

Revision ID: e83ec7313eb4
Revises: d158e734c7bc
Create Date: 2026-08-05 17:09:59.736829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import core.database  # noqa: F401 — для типа StrippedString

# revision identifiers, used by Alembic.
revision: str = 'e83ec7313eb4'
down_revision: Union[str, Sequence[str], None] = 'd158e734c7bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # evidence_url -> url (переименование, заодно обновляем комментарий)
    op.alter_column(
        'source_candidate',
        'evidence_url',
        new_column_name='url',
        existing_type=core.database.StrippedString(length=512),
        comment='Url найденного кандидата к парсингу',
        existing_comment='Ссылка-доказательство: где упомянут конкурент',
        existing_nullable=True,
    )
    op.alter_column(
        'source_candidate',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        comment='Когда агент предложил кандидата',
        existing_comment='Когда агент предложил',
        existing_nullable=False,
        existing_server_default=sa.text('now()'),
    )
    op.drop_constraint(
        'ck_source_candidate_evidence_url_trimmed',
        'source_candidate',
        type_='check',
    )
    op.create_check_constraint(
        'ck_source_candidate_url_trimmed',
        'source_candidate',
        'url = btrim(url)',
    )

    # score — оценка релевантности от LLM, порог сравнения в core.config
    op.add_column(
        'source_candidate',
        sa.Column(
            'score',
            sa.Numeric(3, 2),
            nullable=True,
            comment=(
                'Оценка релевантности от LLM (0.00–1.00). Кандидат '
                'переносится в source, когда score строго больше '
                'настраиваемого порога (core.config.settings.'
                'source_candidate_score_threshold)'
            ),
        ),
    )
    op.create_check_constraint(
        'ck_source_candidate_score_range',
        'source_candidate',
        'score IS NULL OR (score BETWEEN 0 AND 1)',
    )

    # is_active — ActiveMixin, снять кандидата с рассмотрения без удаления
    op.add_column(
        'source_candidate',
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
            comment=(
                'Мягкое выключение записи: не участвует в выборках, '
                'из БД не удаляем'
            ),
        ),
    )

    # Ручная модерация (pending/approved/rejected) отменена в пользу
    # авто-переноса по порогу score — сносим старый status ДО того, как
    # завести новый (тоже 'status', но под новый enum), иначе имя колонки
    # временно продублируется.
    op.drop_constraint(
        'ck_source_candidate_moderated_by_trimmed',
        'source_candidate',
        type_='check',
    )
    op.drop_column('source_candidate', 'llm_assessment')
    op.drop_column('source_candidate', 'status')
    op.drop_column('source_candidate', 'moderated_by')
    op.drop_column('source_candidate', 'moderated_at')
    sa.Enum(name='candidate_status').drop(op.get_bind(), checkfirst=True)

    # Новый status: new -> promoted, проставляется в момент переноса
    # (SourceCandidatePromoter). Индекс — отбор на перенос без JOIN/NOT
    # EXISTS с source при росте таблицы.
    source_candidate_status = sa.Enum(
        'new', 'promoted', name='source_candidate_status'
    )
    source_candidate_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'source_candidate',
        sa.Column(
            'status',
            source_candidate_status,
            server_default=sa.text("'new'"),
            nullable=False,
            comment=(
                'new -> promoted. Проставляется В МОМЕНТ переноса в '
                'source (SourceCandidatePromoter) — отбор кандидатов на '
                'перенос идёт по индексу на status, без JOIN/NOT EXISTS '
                'с source'
            ),
        ),
    )
    op.create_index(
        'ix_source_candidate_status', 'source_candidate', ['status']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_source_candidate_status', table_name='source_candidate')
    op.drop_column('source_candidate', 'status')
    sa.Enum(name='source_candidate_status').drop(op.get_bind(), checkfirst=True)

    candidate_status = sa.Enum(
        'pending', 'approved', 'rejected', name='candidate_status'
    )
    candidate_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'source_candidate',
        sa.Column(
            'moderated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Когда промодерировали',
        ),
    )
    op.add_column(
        'source_candidate',
        sa.Column(
            'moderated_by',
            core.database.StrippedString(length=128),
            nullable=True,
            comment='Кто промодерировал',
        ),
    )
    op.add_column(
        'source_candidate',
        sa.Column(
            'status',
            candidate_status,
            server_default=sa.text("'pending'"),
            nullable=False,
            comment='pending → approved / rejected',
        ),
    )
    op.add_column(
        'source_candidate',
        sa.Column(
            'llm_assessment',
            sa.Text(),
            nullable=True,
            comment='Краткая оценка LLM: что за ресурс, релевантность, публичность',
        ),
    )
    op.create_check_constraint(
        'ck_source_candidate_moderated_by_trimmed',
        'source_candidate',
        'moderated_by = btrim(moderated_by)',
    )

    op.drop_column('source_candidate', 'is_active')

    op.drop_constraint(
        'ck_source_candidate_score_range', 'source_candidate', type_='check'
    )
    op.drop_column('source_candidate', 'score')

    op.drop_constraint(
        'ck_source_candidate_url_trimmed', 'source_candidate', type_='check'
    )
    op.alter_column(
        'source_candidate',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        comment='Когда агент предложил',
        existing_comment='Когда агент предложил кандидата',
        existing_nullable=False,
        existing_server_default=sa.text('now()'),
    )
    op.alter_column(
        'source_candidate',
        'url',
        new_column_name='evidence_url',
        existing_type=core.database.StrippedString(length=512),
        comment='Ссылка-доказательство: где упомянут конкурент',
        existing_comment='Url найденного кандидата к парсингу',
        existing_nullable=True,
    )
    op.create_check_constraint(
        'ck_source_candidate_evidence_url_trimmed',
        'source_candidate',
        'evidence_url = btrim(evidence_url)',
    )
