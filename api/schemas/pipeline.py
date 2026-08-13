"""HTTP schemas for asynchronous pipeline orchestration."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.enums import (
    PipelineRunKind,
    PipelineRunSource,
    PipelineRunStatus,
    PipelineStageStatus,
)


class PipelineRunRequest(BaseModel):
    reparse: bool = False
    true_parsing: bool | None = None


class PipelineStageRunRequest(PipelineRunRequest):
    @model_validator(mode='after')
    def validate_options(self) -> 'PipelineStageRunRequest':
        return self


class PipelineRunAccepted(BaseModel):
    run_id: UUID
    status: PipelineRunStatus


class PipelineStageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: int
    task_id: str | None
    status: PipelineStageStatus
    attempts: int
    is_stub: bool
    reparse: bool
    result: dict | None
    error: dict | None
    started_at: datetime | None
    finished_at: datetime | None


class PipelineRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    kind: PipelineRunKind
    selected_stage: int | None
    source: PipelineRunSource
    status: PipelineRunStatus
    parameters: dict
    root_task_id: str | None
    scheduled_for: datetime | None
    result: dict | None
    error: dict | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    stages: list[PipelineStageRead] = Field(default_factory=list)


class PipelineRunPage(BaseModel):
    items: list[PipelineRunRead]
    total: int
    offset: int
    limit: int


class PipelineScheduleRead(BaseModel):
    enabled: bool
    cron: str
    timezone: str
    enabled_source: str
    cron_source: str
    timezone_source: str
    last_scheduled_for: datetime | None
    previous_slot: datetime
    next_slot: datetime


class PipelineScheduleUpdate(BaseModel):
    enabled: bool | None = None
    cron: str | None = None
    timezone: str | None = None
    reset: bool = False
