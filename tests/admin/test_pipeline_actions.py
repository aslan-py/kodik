"""Pipeline widgets после скрытия marker продолжают звать прежние handlers."""

from unittest.mock import AsyncMock

import pytest
from fastadmin import WidgetActionInputSchema
from fastadmin.models.base import admin_models
from fastadmin.models.schemas import WidgetActionQuerySchema, WidgetType

from core.enums import PipelineRunStatus
from core.pipeline.models import PipelineSchedule
from core.pipeline.service import CreatedPipelineRun


def _pipeline_admin():
    return next(
        admin
        for model, admin in admin_models.items()
        if model.__name__ == 'PipelineControlMarker'
    )


@pytest.mark.parametrize('stage_number', range(1, 8))
async def test_stage_widget_calls_existing_stage_handler(
    monkeypatch, stage_number
):
    handler = AsyncMock()
    monkeypatch.setattr('api.admin.pipeline_control._run_stage_widget', handler)
    payload = WidgetActionInputSchema(query=[])

    await getattr(_pipeline_admin(), f'stage_{stage_number}')(payload)

    handler.assert_awaited_once_with(stage_number, payload)


async def test_run_all_widget_calls_existing_all_stages_handler(monkeypatch):
    enqueue_run = AsyncMock(
        return_value=CreatedPipelineRun(
            run_id='00000000-0000-0000-0000-000000000001',
            status=PipelineRunStatus.queued,
        )
    )
    monkeypatch.setattr(
        'core.pipeline.service.PipelineRunService.enqueue_run', enqueue_run
    )

    response = await _pipeline_admin().run_all_stages(
        WidgetActionInputSchema(query=[])
    )

    enqueue_run.assert_awaited_once()
    assert response.data[0]['status'] == 'queued'


async def test_schedule_widget_saves_and_resets_override(session):
    schedule = await session.get(PipelineSchedule, 1)
    assert schedule is not None
    payload = WidgetActionInputSchema(
        query=[
            WidgetActionQuerySchema('включено', WidgetType.Switch, True),
            WidgetActionQuerySchema('cron', WidgetType.Input, '15 9 * * 1-5'),
            WidgetActionQuerySchema(
                'часовой пояс', WidgetType.Input, 'Europe/Berlin'
            ),
        ]
    )

    response = await _pipeline_admin().save_schedule(payload)
    assert response.data[0]['cron'] == '15 9 * * 1-5'
    assert response.data[0]['enabled_source'] == 'admin'

    response = await _pipeline_admin().reset_schedule(
        WidgetActionInputSchema(query=[])
    )
    assert response.data[0]['enabled_source'] == 'env'
