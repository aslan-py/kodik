"""Durable run creation and active-slot behavior."""

import pytest
from sqlalchemy import select

from core.enums import PipelineRunKind, PipelineRunSource, PipelineRunStatus
from core.pipeline.models import PipelineRun, PipelineStageRun
from core.pipeline.service import PipelineRunConflict, PipelineRunService


@pytest.mark.asyncio
async def test_create_run_snapshots_parameters_and_rejects_active_run(session):
    service = PipelineRunService(session)
    created = await service.create_run(
        kind=PipelineRunKind.single,
        stage=2,
        source=PipelineRunSource.api,
        initiated_by_user_id=None,
        parameters={'reparse': True},
    )

    run = await session.scalar(
        select(PipelineRun).where(PipelineRun.run_id == created.run_id)
    )
    assert created.status == PipelineRunStatus.queued
    assert run is not None
    assert run.parameters == {'reparse': True}
    stage_run = await session.scalar(
        select(PipelineStageRun).where(
            PipelineStageRun.pipeline_run_id == run.id
        )
    )
    assert stage_run is not None
    assert stage_run.stage == 2
    assert stage_run.reparse is True

    with pytest.raises(PipelineRunConflict) as exc_info:
        await service.create_run(
            kind=PipelineRunKind.single,
            stage=3,
            source=PipelineRunSource.cli,
        )
    assert exc_info.value.run_id == created.run_id
