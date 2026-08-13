"""Transactional creation of durable pipeline runs."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery import chain
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import PipelineRunKind, PipelineRunSource, PipelineRunStatus
from core.pipeline.models import PipelineRun, PipelineStageRun
from core.pipeline.registry import STAGES


class PipelineRunConflict(RuntimeError):
    """Raised when another queued or running pipeline run owns the slot."""

    def __init__(self, run_id: UUID):
        self.run_id = run_id
        super().__init__(f'Pipeline is already running: {run_id}')


@dataclass(frozen=True)
class CreatedPipelineRun:
    run_id: UUID
    status: PipelineRunStatus


class PipelineRunService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(
        self,
        *,
        kind: PipelineRunKind,
        source: PipelineRunSource,
        stage: int | None = None,
        initiated_by_user_id: int | None = None,
        parameters: dict[str, Any] | None = None,
        scheduled_for: datetime | None = None,
    ) -> CreatedPipelineRun:
        if kind == PipelineRunKind.single and stage not in STAGES:
            raise ValueError(f'Unknown pipeline stage: {stage}')
        if kind == PipelineRunKind.all and stage is not None:
            raise ValueError('A full pipeline run cannot select one stage')

        active_run = await self.session.scalar(
            select(PipelineRun)
            .where(PipelineRun.active_slot.is_(True))
            .with_for_update()
        )
        if active_run is not None:
            raise PipelineRunConflict(active_run.run_id)

        stages = [stage] if kind == PipelineRunKind.single else sorted(STAGES)
        run = PipelineRun(
            kind=kind,
            selected_stage=stage,
            source=source,
            initiated_by_user_id=initiated_by_user_id,
            parameters=parameters or {},
            scheduled_for=scheduled_for,
        )
        run.stages = [
            PipelineStageRun(
                stage=stage_number,
                reparse=bool((parameters or {}).get('reparse', False)),
                is_stub=(parameters or {}).get('true_parsing') is False,
            )
            for stage_number in stages
        ]
        self.session.add(run)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            active_run = await self.session.scalar(
                select(PipelineRun).where(PipelineRun.active_slot.is_(True))
            )
            if active_run is not None:
                raise PipelineRunConflict(active_run.run_id) from None
            raise
        return CreatedPipelineRun(run_id=run.run_id, status=run.status)

    async def fail_publication(self, run_id: UUID, reason: str) -> None:
        run = await self.session.scalar(
            select(PipelineRun)
            .where(PipelineRun.run_id == run_id)
            .with_for_update()
        )
        if run is None:
            return
        run.status = PipelineRunStatus.failed
        run.active_slot = False
        run.error = {'kind': 'publication', 'message': reason}
        run.finished_at = datetime.now(UTC)
        await self.session.commit()

    async def enqueue_run(
        self,
        *,
        kind: PipelineRunKind,
        source: PipelineRunSource,
        stage: int | None = None,
        initiated_by_user_id: int | None = None,
        parameters: dict[str, Any] | None = None,
        scheduled_for: datetime | None = None,
    ) -> CreatedPipelineRun:
        created = await self.create_run(
            kind=kind,
            source=source,
            stage=stage,
            initiated_by_user_id=initiated_by_user_id,
            parameters=parameters,
            scheduled_for=scheduled_for,
        )
        await self.session.commit()
        try:
            canvas = self._build_canvas(created.run_id, kind, stage)
            async_result = canvas.apply_async()
        except Exception as exc:
            await self.fail_publication(created.run_id, str(exc))
            raise

        run = await self.session.scalar(
            select(PipelineRun).where(PipelineRun.run_id == created.run_id)
        )
        if run is not None:
            run.root_task_id = async_result.id
            await self.session.commit()
        return created

    @staticmethod
    def _build_canvas(run_id: UUID, kind: PipelineRunKind, stage: int | None):
        from core.pipeline.tasks import (
            finalize_pipeline_run,
            mark_pipeline_run_failed,
            run_stage_bp1,
            run_stage_bp2,
            run_stage_bp3,
            run_stage_bp4,
            run_stage_bp5,
            run_stage_bp6,
            run_stage_bp7,
        )

        task_by_stage = {
            1: run_stage_bp1,
            2: run_stage_bp2,
            3: run_stage_bp3,
            4: run_stage_bp4,
            5: run_stage_bp5,
            6: run_stage_bp6,
            7: run_stage_bp7,
        }
        stages = (
            [stage] if kind == PipelineRunKind.single else sorted(task_by_stage)
        )
        errback = mark_pipeline_run_failed.si(str(run_id))
        signatures = []
        for number in stages:
            signature = task_by_stage[number].si(str(run_id))
            signature.link_error(errback)
            signatures.append(signature)
        finalizer = finalize_pipeline_run.si(str(run_id))
        finalizer.link_error(errback)
        signatures.append(finalizer)
        return chain(*signatures)
