"""Schedule resolution and cron edge-case coverage."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.enums import PipelineRunStatus
from core.pipeline.models import PipelineSchedule
from core.pipeline.schedule import (
    InvalidPipelineSchedule,
    _slots,
    get_effective_schedule,
    validate_schedule_values,
)
from core.pipeline.service import CreatedPipelineRun
from core.pipeline.tasks import dispatch_scheduled_pipeline_once


def test_schedule_rejects_invalid_cron_and_timezone():
    with pytest.raises(InvalidPipelineSchedule):
        validate_schedule_values('not a cron', 'Europe/Moscow')
    with pytest.raises(InvalidPipelineSchedule):
        validate_schedule_values('* * * * *', 'Not/AZone')


def test_schedule_slots_are_utc_across_dst_boundary():
    previous, following = _slots(
        '0 * * * *',
        'Europe/Berlin',
        datetime(2026, 10, 25, 1, 30, tzinfo=UTC),
    )
    assert previous.tzinfo is UTC
    assert following.tzinfo is UTC
    assert previous < following


@pytest.mark.asyncio
async def test_db_override_is_effective_without_restart(session):
    schedule = await session.get(PipelineSchedule, 1)
    assert schedule is not None
    schedule.enabled_override = True
    schedule.cron_override = '15 9 * * 1-5'
    schedule.timezone_override = 'Europe/Berlin'

    effective = await get_effective_schedule(session)

    assert effective.enabled is True
    assert effective.enabled_source == 'admin'
    assert effective.cron == '15 9 * * 1-5'
    assert effective.timezone == 'Europe/Berlin'


@pytest.mark.asyncio
async def test_second_beat_poll_does_not_duplicate_cron_slot(
    session, monkeypatch
):
    schedule = await session.get(PipelineSchedule, 1)
    assert schedule is not None
    schedule.enabled_override = True
    schedule.cron_override = '* * * * *'
    schedule.timezone_override = 'UTC'
    enqueue = AsyncMock(
        return_value=CreatedPipelineRun(
            run_id=uuid4(), status=PipelineRunStatus.queued
        )
    )
    monkeypatch.setattr(
        'core.pipeline.service.PipelineRunService.enqueue_run', enqueue
    )

    first = await dispatch_scheduled_pipeline_once(session)
    second = await dispatch_scheduled_pipeline_once(session)

    assert first['scheduled'] is True
    assert second == {'scheduled': False, 'reason': 'slot already processed'}
    enqueue.assert_awaited_once()
