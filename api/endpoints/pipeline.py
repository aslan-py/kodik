"""Authenticated HTTP operations for asynchronous pipeline runs."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from api.dependencies import EditorDep, SessionDep, ViewerDep
from api.schemas.pipeline import (
    PipelineRunAccepted,
    PipelineRunPage,
    PipelineRunRead,
    PipelineRunRequest,
    PipelineScheduleRead,
    PipelineScheduleUpdate,
)
from core.config import settings
from core.enums import PipelineRunKind, PipelineRunSource
from core.pipeline.models import PipelineRun, PipelineSchedule
from core.pipeline.registry import STAGES
from core.pipeline.schedule import (
    InvalidPipelineSchedule,
    get_effective_schedule,
    validate_schedule_values,
)
from core.pipeline.service import PipelineRunConflict, PipelineRunService

router = APIRouter()


def _accepted(created) -> PipelineRunAccepted:
    return PipelineRunAccepted(run_id=created.run_id, status=created.status)


@router.post(
    '/runs',
    response_model=PipelineRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_pipeline_run(
    data: PipelineRunRequest, user: EditorDep, session: SessionDep
) -> PipelineRunAccepted:
    try:
        created = await PipelineRunService(session).enqueue_run(
            kind=PipelineRunKind.all,
            source=PipelineRunSource.api,
            initiated_by_user_id=user.id,
            parameters=data.model_dump(),
        )
    except PipelineRunConflict as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {'run_id': str(exc.run_id)}
        ) from None
    return _accepted(created)


@router.post(
    '/stages/{stage}/runs',
    response_model=PipelineRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_stage_run(
    stage: int, data: PipelineRunRequest, user: EditorDep, session: SessionDep
) -> PipelineRunAccepted:
    if stage not in STAGES:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, 'Pipeline stage not found'
        )
    if data.reparse and stage != 2:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'reparse is supported only by BP2',
        )
    if data.true_parsing is not None and stage != 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'true_parsing is supported only by BP1',
        )
    try:
        created = await PipelineRunService(session).enqueue_run(
            kind=PipelineRunKind.single,
            stage=stage,
            source=PipelineRunSource.api,
            initiated_by_user_id=user.id,
            parameters=data.model_dump(),
        )
    except PipelineRunConflict as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {'run_id': str(exc.run_id)}
        ) from None
    return _accepted(created)


@router.get('/runs', response_model=PipelineRunPage)
async def list_pipeline_runs(
    _user: ViewerDep,
    session: SessionDep,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PipelineRunPage:
    total = await session.scalar(select(func.count()).select_from(PipelineRun))
    runs = (
        await session.scalars(
            select(PipelineRun)
            .options(selectinload(PipelineRun.stages))
            .order_by(PipelineRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return PipelineRunPage(
        items=[PipelineRunRead.model_validate(run) for run in runs],
        total=total or 0,
        offset=offset,
        limit=limit,
    )


@router.get('/runs/{run_id}', response_model=PipelineRunRead)
async def get_pipeline_run(
    run_id: UUID, _user: ViewerDep, session: SessionDep
) -> PipelineRunRead:
    run = await session.scalar(
        select(PipelineRun)
        .where(PipelineRun.run_id == run_id)
        .options(selectinload(PipelineRun.stages))
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Pipeline run not found')
    return PipelineRunRead.model_validate(run)


@router.get('/schedule', response_model=PipelineScheduleRead)
async def get_pipeline_schedule(
    _user: ViewerDep, session: SessionDep
) -> PipelineScheduleRead:
    return PipelineScheduleRead(
        **(await get_effective_schedule(session)).__dict__
    )


@router.patch('/schedule', response_model=PipelineScheduleRead)
async def update_pipeline_schedule(
    data: PipelineScheduleUpdate, user: EditorDep, session: SessionDep
) -> PipelineScheduleRead:
    schedule = await session.scalar(
        select(PipelineSchedule)
        .where(PipelineSchedule.singleton_key == 1)
        .with_for_update()
    )
    if schedule is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            'Pipeline schedule is unavailable',
        )
    if data.reset:
        schedule.enabled_override = None
        schedule.cron_override = None
        schedule.timezone_override = None
    else:
        cron = (
            data.cron
            if data.cron is not None
            else schedule.cron_override or settings.pipeline_schedule_cron
        )
        timezone = (
            data.timezone
            if data.timezone is not None
            else schedule.timezone_override
            or settings.pipeline_schedule_timezone
        )
        try:
            validate_schedule_values(cron, timezone)
        except InvalidPipelineSchedule as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
            ) from None
        if data.enabled is not None:
            schedule.enabled_override = data.enabled
        if data.cron is not None:
            schedule.cron_override = data.cron
        if data.timezone is not None:
            schedule.timezone_override = data.timezone
    schedule.updated_by_user_id = user.id
    await session.commit()
    return PipelineScheduleRead(
        **(await get_effective_schedule(session)).__dict__
    )
