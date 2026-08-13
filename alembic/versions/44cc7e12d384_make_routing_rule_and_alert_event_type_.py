"""make routing_rule and alert event_type optional

Revision ID: 44cc7e12d384
Revises: d2fcfdb80aa9
Create Date: 2026-08-10 22:55:20.053884

Часть openspec/changes/add-priority-only-routing: правило маршрутизации без
типа события срабатывает на любой тип нужного приоритета. Снимаем NOT NULL
с event_type_id в routing_rule и alert; обычный UNIQUE на routing_rule не
трогаем (NULL != NULL в Postgres уже не даёт ему видеть дубли строк без
типа) — вместо этого заводим частичный уникальный индекс на случай "тип не
задан" (тот же приём, что uq_search_task_no_trigger в src/bp1/models.py).

Автогенерация заодно подхватила несвязанный дрейф схемы
source_candidate.domain (NOT NULL в БД против nullable=True в модели) —
известная, ранее отмеченная нестыковка (см. d5a9a93f4f4a), не в скоупе
этого change, сюда не включаем.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44cc7e12d384'
down_revision: Union[str, Sequence[str], None] = 'd2fcfdb80aa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'alert',
        'event_type_id',
        existing_type=sa.INTEGER(),
        nullable=True,
        comment=(
            'Какой тип значимого события распознан. Пусто — сработало '
            'правило по приоритету, тип события распознать не удалось'
        ),
        existing_comment='Какой тип значимого события распознан',
    )
    op.alter_column(
        'routing_rule',
        'event_type_id',
        existing_type=sa.INTEGER(),
        nullable=True,
        comment=(
            'Для какого типа значимого события. Пусто — любой тип события '
            'этого приоритета (правило по приоритету)'
        ),
        existing_comment='Для какого типа значимого события',
    )
    op.create_index(
        'uq_routing_rule_no_type_priority_channel_user',
        'routing_rule',
        ['priority', 'channel_id', 'user_id'],
        unique=True,
        postgresql_where=sa.text('event_type_id IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_routing_rule_no_type_priority_channel_user',
        table_name='routing_rule',
        postgresql_where=sa.text('event_type_id IS NULL'),
    )
    op.alter_column(
        'routing_rule',
        'event_type_id',
        existing_type=sa.INTEGER(),
        nullable=False,
        comment='Для какого типа значимого события',
        existing_comment=(
            'Для какого типа значимого события. Пусто — любой тип события '
            'этого приоритета (правило по приоритету)'
        ),
    )
    op.alter_column(
        'alert',
        'event_type_id',
        existing_type=sa.INTEGER(),
        nullable=False,
        comment='Какой тип значимого события распознан',
        existing_comment=(
            'Какой тип значимого события распознан. Пусто — сработало '
            'правило по приоритету, тип события распознать не удалось'
        ),
    )
