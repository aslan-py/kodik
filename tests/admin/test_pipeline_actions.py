"""Pipeline widgets после скрытия marker продолжают звать прежние handlers."""

from unittest.mock import AsyncMock

import pytest
from fastadmin import WidgetActionInputSchema
from fastadmin.models.base import admin_models

from core.pipeline.runner import StageResult


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
    run_all = AsyncMock(
        return_value=[
            StageResult(
                number=1,
                title='Сбор',
                is_stub=False,
                ok=True,
                result={'processed': 1},
            )
        ]
    )
    monkeypatch.setattr('api.admin.pipeline_control.run_all', run_all)

    response = await _pipeline_admin().run_all_stages(
        WidgetActionInputSchema(query=[])
    )

    run_all.assert_awaited_once_with()
    assert response.data[0]['статус'] == 'OK'
