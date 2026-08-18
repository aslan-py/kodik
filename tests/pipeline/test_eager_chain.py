"""Eager execution checks for the durable BP1--BP7 orchestration canvas."""

import asyncio

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.celery_app import app
from core.enums import (
    PipelineRunKind,
    PipelineRunSource,
    PipelineRunStatus,
    PipelineStageStatus,
)
from core.pipeline import tasks as pipeline_tasks
from core.pipeline.models import PipelineRun
from core.pipeline.runner import StageResult
from core.pipeline.service import PipelineRunService


@pytest.mark.asyncio
@pytest.mark.parametrize('failed_stage', [None, 4])
async def test_eager_full_chain_records_every_stage_and_continues_after_failure(
    engine, session, monkeypatch, failed_stage: int | None
):
    """A stage envelope must keep the chain moving even when one BP fails."""
    calls: list[int] = []
    task_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def fake_run_stage(stage: int, **_: object) -> StageResult:
        calls.append(stage)
        if stage == failed_stage:
            raise RuntimeError(f'BP{stage} failed as expected')
        return StageResult(
            number=stage,
            title=f'BP{stage}',
            is_stub=False,
            ok=True,
            result={'stage': stage},
        )

    monkeypatch.setattr(
        pipeline_tasks, 'AsyncSessionLocal', task_session_factory
    )
    monkeypatch.setattr(pipeline_tasks, 'run_stage', fake_run_stage)
    previous_eager = app.conf.task_always_eager
    previous_propagates = app.conf.task_eager_propagates
    app.conf.update(task_always_eager=True, task_eager_propagates=True)

    created_run_id = None
    try:
        created = await PipelineRunService(session).create_run(
            kind=PipelineRunKind.all,
            source=PipelineRunSource.cli,
        )
        created_run_id = created.run_id
        await session.commit()

        canvas = PipelineRunService._build_canvas(
            created.run_id, PipelineRunKind.all, None
        )
        await asyncio.to_thread(canvas.apply_async)

        async with task_session_factory() as verification_session:
            run = await verification_session.scalar(
                select(PipelineRun).where(PipelineRun.run_id == created.run_id)
            )
            assert run is not None
            await verification_session.refresh(run, ['stages'])
            assert calls == list(range(1, 8))
            expected_status = (
                PipelineRunStatus.partial_failed
                if failed_stage is not None
                else PipelineRunStatus.succeeded
            )
            assert run.status == expected_status
            assert run.active_slot is False
            assert all(stage.task_id for stage in run.stages)
            assert [stage.status for stage in run.stages] == [
                (
                    PipelineStageStatus.failed
                    if stage.stage == failed_stage
                    else PipelineStageStatus.succeeded
                )
                for stage in run.stages
            ]
    finally:
        if created_run_id is not None:
            async with task_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    delete(PipelineRun).where(
                        PipelineRun.run_id == created_run_id
                    )
                )
                await cleanup_session.commit()
        app.conf.update(
            task_always_eager=previous_eager,
            task_eager_propagates=previous_propagates,
        )
