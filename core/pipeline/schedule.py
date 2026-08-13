"""Effective pipeline schedule derived from env defaults and DB overrides."""

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.pipeline.models import PipelineSchedule


class InvalidPipelineSchedule(ValueError):
    """A cron expression or IANA timezone cannot be used by the scheduler."""


@dataclass(frozen=True)
class EffectiveSchedule:
    enabled: bool
    cron: str
    timezone: str
    enabled_source: str
    cron_source: str
    timezone_source: str
    last_scheduled_for: datetime | None
    previous_slot: datetime
    next_slot: datetime


def validate_schedule_values(cron: str, timezone: str) -> None:
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise InvalidPipelineSchedule(
            f'Unknown IANA timezone: {timezone}'
        ) from exc
    if not croniter.is_valid(cron):
        raise InvalidPipelineSchedule(f'Invalid cron expression: {cron}')


def _slots(
    cron: str, timezone: str, now: datetime
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    local_now = now.astimezone(zone)
    previous = croniter(cron, local_now).get_prev(datetime)
    following = croniter(cron, local_now).get_next(datetime)
    return previous.astimezone(UTC), following.astimezone(UTC)


async def get_effective_schedule(
    session: AsyncSession, *, now: datetime | None = None
) -> EffectiveSchedule:
    """Resolve each field as DB override first, then its environment default."""
    schedule = await session.get(PipelineSchedule, 1)
    enabled = (
        schedule.enabled_override
        if schedule and schedule.enabled_override is not None
        else settings.pipeline_schedule_enabled
    )
    cron = (
        schedule.cron_override
        if schedule and schedule.cron_override is not None
        else settings.pipeline_schedule_cron
    )
    timezone = (
        schedule.timezone_override
        if schedule and schedule.timezone_override is not None
        else settings.pipeline_schedule_timezone
    )
    validate_schedule_values(cron, timezone)
    previous_slot, next_slot = _slots(cron, timezone, now or datetime.now(UTC))
    return EffectiveSchedule(
        enabled=enabled,
        cron=cron,
        timezone=timezone,
        enabled_source=(
            'admin'
            if schedule and schedule.enabled_override is not None
            else 'env'
        ),
        cron_source=(
            'admin'
            if schedule and schedule.cron_override is not None
            else 'env'
        ),
        timezone_source=(
            'admin'
            if schedule and schedule.timezone_override is not None
            else 'env'
        ),
        last_scheduled_for=schedule.last_scheduled_for if schedule else None,
        previous_slot=previous_slot,
        next_slot=next_slot,
    )
