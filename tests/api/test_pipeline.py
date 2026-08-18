"""HTTP contract tests for pipeline orchestration endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.enums import (
    PipelineRunKind,
    PipelineRunSource,
    PipelineRunStatus,
    PipelineStageStatus,
    UserRole,
)
from core.pipeline.models import PipelineRun, PipelineStageRun
from core.pipeline.service import CreatedPipelineRun, PipelineRunConflict


@pytest.mark.asyncio
async def test_stage_run_validates_role_stage_and_parameters(
    client, users_by_role, auth_headers
):
    viewer = users_by_role[UserRole.viewer]
    analyst = users_by_role[UserRole.analyst]

    response = await client.post(
        '/pipeline/stages/1/runs', headers=auth_headers(viewer), json={}
    )
    assert response.status_code == 403

    response = await client.post(
        '/pipeline/stages/8/runs', headers=auth_headers(analyst), json={}
    )
    assert response.status_code == 404

    response = await client.post(
        '/pipeline/stages/3/runs',
        headers=auth_headers(analyst),
        json={'reparse': True},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_run_endpoint_returns_accepted_run_id(
    client, users_by_role, auth_headers, monkeypatch
):
    run_id = uuid4()
    enqueue_run = AsyncMock(
        return_value=CreatedPipelineRun(
            run_id=run_id, status=PipelineRunStatus.queued
        )
    )
    monkeypatch.setattr(
        'core.pipeline.service.PipelineRunService.enqueue_run', enqueue_run
    )

    response = await client.post(
        '/pipeline/runs',
        headers=auth_headers(users_by_role[UserRole.analyst]),
        json={'true_parsing': False},
    )

    assert response.status_code == 202
    assert response.json() == {'run_id': str(run_id), 'status': 'queued'}
    assert enqueue_run.await_args.kwargs['parameters'] == {
        'reparse': False,
        'true_parsing': False,
    }


@pytest.mark.asyncio
async def test_run_endpoint_returns_active_run_conflict(
    client, users_by_role, auth_headers, monkeypatch
):
    active_run_id = uuid4()
    enqueue_run = AsyncMock(side_effect=PipelineRunConflict(active_run_id))
    monkeypatch.setattr(
        'core.pipeline.service.PipelineRunService.enqueue_run', enqueue_run
    )

    response = await client.post(
        '/pipeline/runs',
        headers=auth_headers(users_by_role[UserRole.analyst]),
        json={},
    )

    assert response.status_code == 409
    assert response.json()['detail']['run_id'] == str(active_run_id)


@pytest.mark.asyncio
async def test_run_history_is_paginated_and_includes_stage_details(
    client, session, users_by_role, auth_headers
):
    run = PipelineRun(
        kind=PipelineRunKind.single,
        selected_stage=2,
        source=PipelineRunSource.api,
        status=PipelineRunStatus.succeeded,
        active_slot=False,
        created_at=datetime.now(UTC),
    )
    run.stages = [
        PipelineStageRun(
            stage=2,
            status=PipelineStageStatus.succeeded,
            attempts=1,
            reparse=True,
        )
    ]
    session.add(run)
    await session.flush()

    headers = auth_headers(users_by_role[UserRole.viewer])
    response = await client.get('/pipeline/runs?limit=1', headers=headers)
    assert response.status_code == 200
    assert response.json()['total'] >= 1

    response = await client.get(f'/pipeline/runs/{run.run_id}', headers=headers)
    assert response.status_code == 200
    assert response.json()['stages'][0]['stage'] == 2
    assert response.json()['stages'][0]['reparse'] is True


@pytest.mark.asyncio
async def test_schedule_override_and_reset(client, users_by_role, auth_headers):
    analyst_headers = auth_headers(users_by_role[UserRole.analyst])
    response = await client.patch(
        '/pipeline/schedule',
        headers=analyst_headers,
        json={
            'enabled': True,
            'cron': '15 9 * * 1-5',
            'timezone': 'Europe/Berlin',
        },
    )
    assert response.status_code == 200
    assert response.json()['enabled_source'] == 'admin'
    assert response.json()['cron'] == '15 9 * * 1-5'

    response = await client.patch(
        '/pipeline/schedule', headers=analyst_headers, json={'reset': True}
    )
    assert response.status_code == 200
    assert response.json()['enabled_source'] == 'env'
