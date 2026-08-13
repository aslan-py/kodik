"""Celery entry points for persisted pipeline-stage executions."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.celery_app import app
from core.config import settings
from core.database import AsyncSessionLocal, engine
from core.enums import (
    PipelineRunKind,
    PipelineRunSource,
    PipelineRunStatus,
    PipelineStageStatus,
)
from core.pipeline.errors import PipelineError
from core.pipeline.models import PipelineRun, PipelineSchedule, PipelineStageRun
from core.pipeline.runner import run_stage
from core.pipeline.schedule import get_effective_schedule
from core.pipeline.service import PipelineRunConflict, PipelineRunService


def _run_async(coroutine):
    """Run one async Celery task without reusing another loop's connection."""
    # Celery prefork children execute each synchronous task through a fresh
    # ``asyncio.run`` loop.  A pooled asyncpg connection belongs to its creating
    # loop, so discard idle connections before creating the next one.
    engine.sync_engine.dispose(close=False)
    return asyncio.run(coroutine)


async def _run_stage_task(
    task_id: str | None, run_id: str, stage: int
) -> dict[str, object]:
    """Run one persisted stage once; terminal redelivery is a harmless no-op."""
    async with AsyncSessionLocal() as session:
        run = await session.scalar(
            select(PipelineRun)
            .where(PipelineRun.run_id == UUID(run_id))
            .with_for_update()
        )
        if run is None:
            return {
                'ok': False,
                'stage': stage,
                'error': 'Pipeline run not found',
            }
        stage_run = await session.scalar(
            select(PipelineStageRun)
            .where(
                PipelineStageRun.pipeline_run_id == run.id,
                PipelineStageRun.stage == stage,
            )
            .with_for_update()
        )
        if stage_run is None:
            return {'ok': False, 'stage': stage, 'error': 'Stage run not found'}
        if stage_run.status in {
            PipelineStageStatus.succeeded,
            PipelineStageStatus.failed,
            PipelineStageStatus.skipped,
        }:
            return {
                'ok': stage_run.status == PipelineStageStatus.succeeded,
                'stage': stage,
            }

        now = datetime.now(UTC)
        run.status = PipelineRunStatus.running
        run.started_at = run.started_at or now
        run.heartbeat_at = now
        stage_run.status = PipelineStageStatus.running
        stage_run.task_id = task_id
        stage_run.attempts += 1
        stage_run.started_at = stage_run.started_at or now
        stage_run.heartbeat_at = now
        await session.commit()

    try:
        parameters = run.parameters
        outcome = await run_stage(
            stage,
            reparse=(
                bool(parameters.get('reparse', False)) if stage == 2 else False
            ),
            true_parsing=parameters.get('true_parsing') if stage == 1 else None,
        )
        envelope: dict[str, object] = {
            'ok': True,
            'stage': stage,
            'result': outcome.result or {},
            'is_stub': outcome.is_stub,
        }
    except Exception as exc:
        envelope = {
            'ok': False,
            'stage': stage,
            'error': str(exc),
            'error_kind': (
                exc.__class__.__name__
                if isinstance(exc, PipelineError)
                else 'unexpected'
            ),
        }

    async with AsyncSessionLocal() as session:
        stage_run = await session.scalar(
            select(PipelineStageRun)
            .where(
                PipelineStageRun.pipeline_run_id == run.id,
                PipelineStageRun.stage == stage,
            )
            .with_for_update()
        )
        if stage_run is None:
            return envelope
        stage_run.heartbeat_at = datetime.now(UTC)
        stage_run.finished_at = stage_run.heartbeat_at
        if envelope['ok']:
            stage_run.status = PipelineStageStatus.succeeded
            stage_run.result = envelope['result']
            stage_run.is_stub = bool(envelope['is_stub'])
        else:
            stage_run.status = PipelineStageStatus.failed
            stage_run.error = {
                'kind': envelope['error_kind'],
                'message': envelope['error'],
            }
        await session.commit()
    return envelope


def _stage_task(stage: int):
    @app.task(name=f'core.pipeline.tasks.run_stage_bp{stage}', bind=True)
    def task(self, run_id: str) -> dict[str, object]:
        return _run_async(_run_stage_task(self.request.id, run_id, stage))

    return task


run_stage_bp1 = _stage_task(1)
run_stage_bp2 = _stage_task(2)
run_stage_bp3 = _stage_task(3)
run_stage_bp4 = _stage_task(4)
run_stage_bp5 = _stage_task(5)
run_stage_bp6 = _stage_task(6)
run_stage_bp7 = _stage_task(7)


@app.task(name='core.pipeline.tasks.finalize_pipeline_run')
def finalize_pipeline_run(run_id: str) -> dict[str, object]:
    return _run_async(_finalize_pipeline_run(run_id))


@app.task(name='core.pipeline.tasks.mark_pipeline_run_failed')
def mark_pipeline_run_failed(run_id: str) -> dict[str, object]:
    return _run_async(_mark_pipeline_run_failed(run_id))


async def _mark_pipeline_run_failed(run_id: str) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        run = await session.scalar(
            select(PipelineRun)
            .where(PipelineRun.run_id == UUID(run_id))
            .with_for_update()
        )
        if run is None or not run.active_slot:
            return {'updated': False}
        run.status = PipelineRunStatus.failed
        run.active_slot = False
        run.finished_at = datetime.now(UTC)
        run.error = {
            'kind': 'celery_errback',
            'message': (
                'A Celery task failed before its stage envelope was saved'
            ),
        }
        await session.commit()
        return {'updated': True}


async def _finalize_pipeline_run(run_id: str) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        run = await session.scalar(
            select(PipelineRun)
            .where(PipelineRun.run_id == UUID(run_id))
            .options(selectinload(PipelineRun.stages))
            .with_for_update()
        )
        if run is None:
            return {'ok': False, 'error': 'Pipeline run not found'}
        failures = [
            stage
            for stage in run.stages
            if stage.status == PipelineStageStatus.failed
        ]
        run.status = (
            PipelineRunStatus.partial_failed
            if failures
            else PipelineRunStatus.succeeded
        )
        run.active_slot = False
        run.finished_at = datetime.now(UTC)
        run.heartbeat_at = run.finished_at
        run.result = {
            'stages': [
                {'stage': stage.stage, 'status': stage.status.value}
                for stage in run.stages
            ]
        }
        await session.commit()
        return {'ok': not failures, 'status': run.status.value}


@app.task(name='core.pipeline.tasks.dispatch_scheduled_pipeline')
def dispatch_scheduled_pipeline() -> dict[str, object]:
    return _run_async(_dispatch_scheduled_pipeline())


async def _dispatch_scheduled_pipeline() -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        return await dispatch_scheduled_pipeline_once(session)


async def dispatch_scheduled_pipeline_once(
    session,
) -> dict[str, object]:
    """Execute one Beat poll; separated for transaction-level testing."""
    schedule = await session.scalar(
        select(PipelineSchedule)
        .where(PipelineSchedule.singleton_key == 1)
        .with_for_update()
    )
    if schedule is None:
        return {'scheduled': False, 'reason': 'schedule row is missing'}
    effective = await get_effective_schedule(session)
    if not effective.enabled:
        return {'scheduled': False, 'reason': 'schedule is disabled'}
    if (
        schedule.last_scheduled_for is not None
        and schedule.last_scheduled_for >= effective.previous_slot
    ):
        return {'scheduled': False, 'reason': 'slot already processed'}
    schedule.last_scheduled_for = effective.previous_slot
    try:
        created = await PipelineRunService(session).enqueue_run(
            kind=PipelineRunKind.all,
            source=PipelineRunSource.beat,
            scheduled_for=effective.previous_slot,
        )
    except PipelineRunConflict as exc:
        await session.commit()
        return {
            'scheduled': False,
            'reason': 'pipeline is busy',
            'active_run_id': str(exc.run_id),
        }
    return {'scheduled': True, 'run_id': str(created.run_id)}


@app.task(name='core.pipeline.tasks.watch_stale_pipeline_runs')
def watch_stale_pipeline_runs() -> int:
    return _run_async(_watch_stale_pipeline_runs())


async def _watch_stale_pipeline_runs() -> int:
    cutoff = (
        datetime.now(UTC).timestamp()
        - settings.pipeline_run_stale_timeout_seconds
    )
    async with AsyncSessionLocal() as session:
        runs = (
            await session.scalars(
                select(PipelineRun)
                .where(
                    PipelineRun.active_slot.is_(True),
                    PipelineRun.heartbeat_at.is_not(None),
                )
                .with_for_update()
            )
        ).all()
        stale_runs = [
            run
            for run in runs
            if run.heartbeat_at and run.heartbeat_at.timestamp() < cutoff
        ]
        for run in stale_runs:
            run.status = PipelineRunStatus.stale
            run.active_slot = False
            run.finished_at = datetime.now(UTC)
            run.error = {
                'kind': 'watchdog',
                'message': 'Pipeline heartbeat timed out',
            }
        await session.commit()
        return len(stale_runs)


@app.task(name='core.pipeline.tasks.reconcile_unpublished_pipeline_runs')
def reconcile_unpublished_pipeline_runs() -> int:
    return _run_async(_reconcile_unpublished_pipeline_runs())


async def _reconcile_unpublished_pipeline_runs() -> int:
    """Terminally resolve committed runs whose canvas was not published."""
    async with AsyncSessionLocal() as session:
        runs = (
            await session.scalars(
                select(PipelineRun)
                .where(
                    PipelineRun.status == PipelineRunStatus.queued,
                    PipelineRun.active_slot.is_(True),
                    PipelineRun.root_task_id.is_(None),
                )
                .with_for_update()
            )
        ).all()
        for run in runs:
            run.status = PipelineRunStatus.failed
            run.active_slot = False
            run.finished_at = datetime.now(UTC)
            run.error = {
                'kind': 'reconciler',
                'message': 'Canvas publication was not confirmed',
            }
        await session.commit()
        return len(runs)
