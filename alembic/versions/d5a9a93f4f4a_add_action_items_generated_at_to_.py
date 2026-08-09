"""add action_items_generated_at to showcase_event

Revision ID: d5a9a93f4f4a
Revises: afbc57e951f4
Create Date: 2026-08-08 21:12:53.900395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5a9a93f4f4a'
down_revision: Union[str, Sequence[str], None] = 'afbc57e951f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Только новая колонка watermark для BP-6. Автогенерация заодно
    # подхватила несвязанный дрейф схемы source_candidate.domain (снятие
    # UNIQUE) — известная, ранее отмеченная нестыковка модели/БД, не в
    # скоупе этого change, сюда не включаем.
    op.add_column('showcase_event', sa.Column('action_items_generated_at', sa.DateTime(timezone=True), nullable=True, comment='Когда BP-6 перенёс задачи из categorized_event.task в action_item — НЕЗАВИСИМО от результата (даже если задач не было). Отбор BP-6: priority IN (П1, П2) AND action_items_generated_at IS NULL — БЕЗ реакции на updated_at (в отличие от alerted_at): повторная переразметка события не должна задвоить/переписать уже заведённые вручную action_item'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('showcase_event', 'action_items_generated_at')
