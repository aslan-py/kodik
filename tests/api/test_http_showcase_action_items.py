"""HTTP-сценарии витрины и плана действий."""

from sqlalchemy import select

from core.enums import ActionStatus, UserRole
from src.bp3.models import CategorizedEvent
from tests.api.test_action_items import make_department, make_showcase_event
from tests.api.test_showcase_crud import make_event


async def test_showcase_list_detail_filter_and_update(
    client, session, users_by_role, auth_headers
):
    event = await make_event(session, title='HTTP Showcase marker')
    editor_headers = auth_headers(users_by_role[UserRole.analyst])
    viewer_headers = auth_headers(users_by_role[UserRole.viewer])

    listed = await client.get(
        '/showcase', params={'title': 'marker'}, headers=viewer_headers
    )
    detail = await client.get(f'/showcase/{event.id}', headers=viewer_headers)
    updated = await client.patch(
        f'/showcase/{event.id}',
        headers=editor_headers,
        json={'comment': 'HTTP verified'},
    )

    assert event.id in {item['id'] for item in listed.json()}
    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()['comment'] == 'HTTP verified'
    categorized = await session.scalar(
        select(CategorizedEvent).where(
            CategorizedEvent.id == event.categorized_event_id
        )
    )
    assert categorized.comment == 'HTTP verified'
    assert (
        await client.patch(
            f'/showcase/{event.id}', headers=editor_headers, json={}
        )
    ).status_code == 422


async def test_action_item_create_viewer_scope_and_update(
    client, session, users_by_role, auth_headers
):
    department = await make_department(session)
    event = await make_showcase_event(session)
    viewer = users_by_role[UserRole.viewer]
    viewer.department_id = department.id
    editor_headers = auth_headers(users_by_role[UserRole.admin])
    viewer_headers = auth_headers(viewer)
    created = await client.post(
        '/action-items',
        headers=editor_headers,
        json={
            'showcase_event_id': event.id,
            'task': 'HTTP task',
            'department_id': department.id,
        },
    )
    item_id = created.json()['id']
    listed = await client.get('/action-items', headers=viewer_headers)
    detail = await client.get(
        f'/action-items/{item_id}', headers=viewer_headers
    )
    updated = await client.patch(
        f'/action-items/{item_id}',
        headers=viewer_headers,
        json={
            'status': ActionStatus.in_progress.value,
            'task': 'must stay unchanged',
        },
    )

    assert created.status_code == 201
    assert item_id in {item['id'] for item in listed.json()}
    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()['status'] == ActionStatus.in_progress
    assert updated.json()['task'] == 'HTTP task'


async def test_action_item_editor_update_and_conflict(
    client, session, users_by_role, auth_headers
):
    own_department = await make_department(session)
    other_department = await make_department(session)
    event = await make_showcase_event(session)
    viewer = users_by_role[UserRole.viewer]
    viewer.department_id = own_department.id
    assigned = users_by_role[UserRole.pending]
    assigned.department_id = other_department.id
    editor_headers = auth_headers(users_by_role[UserRole.analyst])
    viewer_headers = auth_headers(viewer)
    created = await client.post(
        '/action-items',
        headers=editor_headers,
        json={
            'showcase_event_id': event.id,
            'task': 'Other department task',
            'department_id': other_department.id,
        },
    )
    item_id = created.json()['id']

    assert (
        await client.get(f'/action-items/{item_id}', headers=viewer_headers)
    ).status_code == 404
    editor_update = await client.patch(
        f'/action-items/{item_id}',
        headers=editor_headers,
        json={'task': 'Editor changed'},
    )
    conflict = await client.patch(
        f'/action-items/{item_id}',
        headers=editor_headers,
        json={
            'department_id': own_department.id,
            'assigned_user_id': assigned.id,
        },
    )
    assert editor_update.status_code == 200
    assert editor_update.json()['task'] == 'Editor changed'
    assert conflict.status_code == 409
