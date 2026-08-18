"""Модель-маркер для админки раннера этапов.

`PipelineControlMarker` не хранит данных — в таблице никогда не будет ни
одной строки. Единственная причина существования: FastAdmin `@register()`
требует настоящую SQLAlchemy-модель, чтобы прицепить к ней кнопки запуска
этапов (`@widget_action`, см. api/admin/pipeline_control.py) — виджетов
самих по себе, без модели-хозяина, библиотека не поддерживает.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, Mixin
from core.enums import (
    PipelineRunKind,
    PipelineRunSource,
    PipelineRunStatus,
    PipelineStageStatus,
    pipeline_run_kind,
    pipeline_run_source,
    pipeline_run_status,
    pipeline_stage_status,
)


class PipelineControlMarker(Base, Mixin):
    """Пустой якорь для страницы «Пайплайн» в админке. Данных не хранит."""

    def __str__(self) -> str:
        return 'Управление пайплайном'


class PipelineRun(Base, Mixin):
    """Durable record of one queued or completed pipeline execution."""

    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), default=uuid4, unique=True, index=True
    )
    kind: Mapped[PipelineRunKind] = mapped_column(pipeline_run_kind)
    selected_stage: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[PipelineRunSource] = mapped_column(pipeline_run_source)
    initiated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey('user.id', ondelete='SET NULL')
    )
    parameters: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    root_task_id: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        pipeline_run_status,
        default=PipelineRunStatus.queued,
        server_default=text("'queued'"),
    )
    active_slot: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text('true')
    )
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    stages: Mapped[list['PipelineStageRun']] = relationship(
        back_populates='pipeline_run',
        cascade='all, delete-orphan',
        order_by='PipelineStageRun.stage',
    )

    __table_args__ = (
        Index(
            'uq_pipeline_run_active_slot',
            'active_slot',
            unique=True,
            postgresql_where=text('active_slot'),
        ),
        Index('ix_pipeline_run_status_created_at', 'status', 'created_at'),
    )


class PipelineStageRun(Base, Mixin):
    """A single BP1--BP7 execution recorded inside a pipeline run."""

    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey('pipeline_run.id', ondelete='CASCADE')
    )
    stage: Mapped[int] = mapped_column(Integer)
    task_id: Mapped[str | None] = mapped_column(Text, index=True)
    status: Mapped[PipelineStageStatus] = mapped_column(
        pipeline_stage_status,
        default=PipelineStageStatus.queued,
        server_default=text("'queued'"),
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text('0')
    )
    is_stub: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text('false')
    )
    reparse: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text('false')
    )
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    pipeline_run: Mapped['PipelineRun'] = relationship(back_populates='stages')

    __table_args__ = (
        UniqueConstraint(
            'pipeline_run_id', 'stage', name='uq_pipeline_stage_run_run_stage'
        ),
    )


class PipelineSchedule(Base, Mixin):
    """Singleton runtime overrides for the environment-backed schedule."""

    singleton_key: Mapped[int] = mapped_column(
        Integer, unique=True, default=1, server_default=text('1')
    )
    enabled_override: Mapped[bool | None] = mapped_column(Boolean)
    cron_override: Mapped[str | None] = mapped_column(Text)
    timezone_override: Mapped[str | None] = mapped_column(Text)
    last_scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey('user.id', ondelete='SET NULL')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            'singleton_key', name='uq_pipeline_schedule_singleton'
        ),
    )
