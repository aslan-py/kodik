"""sync source_candidate domain unique drift

Revision ID: d8be5a20d9b1
Revises: d5a9a93f4f4a
Create Date: 2026-08-10 21:34:01.068492

Модель `SourceCandidate.domain` (src/bp7/models.py) объявлена `unique=False` ещё
в 52e13722df84 ("init2"), но на части БД (в т.ч. локальной) UNIQUE-констрейнт
`source_candidate_domain_key` физически остался — известный, ранее отмеченный
дрейф (см. комментарий в d5a9a93f4f4a). SourceFinderModule (BP-3) в рамках
одного прогона может вернуть несколько кандидатов с одинаковым доменом —
с этим констрейнтом batch-INSERT в SaveResultsModule падает с
UniqueViolationError.

DROP CONSTRAINT IF EXISTS (raw SQL, не op.drop_constraint) — потому что
`alembic_version` не отражает фактическое состояние объекта в конкретной БД:
на части окружений констрейнта уже может не быть, и обычный
op.drop_constraint там упал бы с "constraint does not exist".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8be5a20d9b1'
down_revision: Union[str, Sequence[str], None] = 'd5a9a93f4f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        'ALTER TABLE source_candidate '
        'DROP CONSTRAINT IF EXISTS source_candidate_domain_key'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Упадёт, если к этому моменту в таблице уже есть дубли domain — ожидаемо
    # для даунгрейда, вручную дедуплицировать данные перед откатом.
    op.execute(
        'ALTER TABLE source_candidate '
        'ADD CONSTRAINT source_candidate_domain_key UNIQUE (domain)'
    )
