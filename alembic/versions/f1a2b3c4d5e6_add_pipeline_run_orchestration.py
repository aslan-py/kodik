"""add durable pipeline-run orchestration tables

Revision ID: f1a2b3c4d5e6
Revises: e1c9e6882eb4
Create Date: 2026-08-13 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'f1a2b3c4d5e6'
down_revision: str | Sequence[str] | None = 'e1c9e6882eb4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


pipeline_run_kind = postgresql.ENUM(
    'single', 'all', name='pipeline_run_kind', create_type=False
)
pipeline_run_source = postgresql.ENUM(
    'admin', 'api', 'cli', 'beat', name='pipeline_run_source', create_type=False
)
pipeline_run_status = postgresql.ENUM(
    'queued',
    'running',
    'succeeded',
    'partial_failed',
    'failed',
    'rejected',
    'stale',
    name='pipeline_run_status',
    create_type=False,
)
pipeline_stage_status = postgresql.ENUM(
    'queued',
    'running',
    'succeeded',
    'failed',
    'skipped',
    name='pipeline_stage_status',
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        pipeline_run_kind,
        pipeline_run_source,
        pipeline_run_status,
        pipeline_stage_status,
    ):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        'pipeline_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', pipeline_run_kind, nullable=False),
        sa.Column('selected_stage', sa.Integer(), nullable=True),
        sa.Column('source', pipeline_run_source, nullable=False),
        sa.Column('initiated_by_user_id', sa.Integer(), nullable=True),
        sa.Column(
            'parameters',
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column('root_task_id', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'status',
            pipeline_run_status,
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            'active_slot',
            sa.Boolean(),
            server_default=sa.text('true'),
            nullable=False,
        ),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error', postgresql.JSONB(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['initiated_by_user_id'], ['user.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id'),
    )
    op.create_index('ix_pipeline_run_run_id', 'pipeline_run', ['run_id'])
    op.create_index(
        'ix_pipeline_run_status_created_at',
        'pipeline_run',
        ['status', 'created_at'],
    )
    op.create_index(
        'uq_pipeline_run_active_slot',
        'pipeline_run',
        ['active_slot'],
        unique=True,
        postgresql_where=sa.text('active_slot'),
    )

    op.create_table(
        'pipeline_stage_run',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pipeline_run_id', sa.Integer(), nullable=False),
        sa.Column('stage', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Text(), nullable=True),
        sa.Column(
            'status',
            pipeline_stage_status,
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            'attempts',
            sa.Integer(),
            server_default=sa.text('0'),
            nullable=False,
        ),
        sa.Column(
            'is_stub',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
        sa.Column(
            'reparse',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error', postgresql.JSONB(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['pipeline_run_id'], ['pipeline_run.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'pipeline_run_id', 'stage', name='uq_pipeline_stage_run_run_stage'
        ),
    )
    op.create_index(
        'ix_pipeline_stage_run_task_id', 'pipeline_stage_run', ['task_id']
    )

    op.create_table(
        'pipeline_schedule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'singleton_key',
            sa.Integer(),
            server_default=sa.text('1'),
            nullable=False,
        ),
        sa.Column('enabled_override', sa.Boolean(), nullable=True),
        sa.Column('cron_override', sa.Text(), nullable=True),
        sa.Column('timezone_override', sa.Text(), nullable=True),
        sa.Column(
            'last_scheduled_for', sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'], ['user.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'singleton_key', name='uq_pipeline_schedule_singleton'
        ),
    )
    op.execute('INSERT INTO pipeline_schedule (singleton_key) VALUES (1)')


def downgrade() -> None:
    op.drop_table('pipeline_schedule')
    op.drop_index(
        'ix_pipeline_stage_run_task_id', table_name='pipeline_stage_run'
    )
    op.drop_table('pipeline_stage_run')
    op.drop_index('uq_pipeline_run_active_slot', table_name='pipeline_run')
    op.drop_index(
        'ix_pipeline_run_status_created_at', table_name='pipeline_run'
    )
    op.drop_index('ix_pipeline_run_run_id', table_name='pipeline_run')
    op.drop_table('pipeline_run')

    bind = op.get_bind()
    for enum_type in (
        pipeline_stage_status,
        pipeline_run_status,
        pipeline_run_source,
        pipeline_run_kind,
    ):
        enum_type.drop(bind, checkfirst=True)
