"""HTTP-контракт вариантов фильтров и применимость action-значений."""

from datetime import date

import pytest
from sqlalchemy import delete

from api.crud.action_items import ActionItemCRUD
from api.main import app
from api.schemas.action_items import ActionItemCreate
from core.enums import ActionStatus, UserRole
from src.bp4.models import ShowcaseEvent
from src.bp6.models import ActionItem
from tests.api.test_action_items import make_department, make_showcase_event


async def _create_option_data(session, users_by_role):
    own_department = await make_department(session)
    other_department = await make_department(session)
    viewer = users_by_role[UserRole.viewer]
    viewer.department_id = own_department.id
    own_assignee = users_by_role[UserRole.pending]
    own_assignee.department_id = own_department.id
    own_assignee.full_name = 'Борис Соболев'
    other_assignee = users_by_role[UserRole.admin]
    other_assignee.department_id = other_department.id
    other_assignee.full_name = 'Анна Ярова'

    own_event = await make_showcase_event(session, title='Own options')
    own_event.category = 'логистика'
    own_event.region = 'Москва'
    own_event.competitor = 'Ozon'
    own_event.media = 'РБК'
    own_event.department = own_department.name
    own_event.priority = 'П2'
    duplicate_event = await make_showcase_event(session, title='Duplicate')
    duplicate_event.category = 'логистика'
    duplicate_event.region = 'Москва'
    duplicate_event.competitor = None
    duplicate_event.media = 'РБК'
    duplicate_event.department = None
    duplicate_event.priority = 'П1'
    other_event = await make_showcase_event(session, title='Other options')
    other_event.category = 'Аналитика'
    other_event.region = 'Архангельск'
    other_event.competitor = 'Wildberries'
    other_event.media = 'Коммерсант'
    other_event.department = other_department.name
    other_event.priority = 'П4'

    crud = ActionItemCRUD(session)
    own_item = await crud.create(
        ActionItemCreate(
            showcase_event_id=own_event.id,
            task='Own option task',
            department_id=own_department.id,
            assigned_user_id=own_assignee.id,
            deadline=date(2026, 8, 14),
        )
    )
    await crud.create(
        ActionItemCreate(
            showcase_event_id=other_event.id,
            task='Other option task',
            department_id=other_department.id,
            assigned_user_id=other_assignee.id,
            deadline=date(2026, 8, 15),
        )
    )
    return viewer, own_item, own_department, other_department


async def test_filter_options_exact_structure_sorting_and_deduplication(
    client, session, users_by_role, auth_headers
):
    _, _, own_department, other_department = await _create_option_data(
        session, users_by_role
    )
    headers = auth_headers(users_by_role[UserRole.analyst])

    first = await client.get('/filter-options', headers=headers)
    second = await client.get('/filter-options', headers=headers)

    assert first.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert set(body) == {'showcase', 'action_items'}
    assert set(body['showcase']) == {
        'category',
        'region',
        'priority',
        'competitor',
        'department',
        'media',
    }
    assert set(body['action_items']) == {
        'status',
        'deadline',
        'priority',
        'assigned_user_id',
        'department_id',
    }
    assert body['showcase']['priority'] == ['П1', 'П2', 'П3', 'П4']
    assert body['showcase']['category'] == ['Аналитика', 'логистика']
    assert body['showcase']['region'] == ['Архангельск', 'Москва']
    assert body['showcase']['competitor'] == ['Ozon', 'Wildberries']
    assert body['showcase']['media'] == ['Коммерсант', 'РБК']
    assert None not in body['showcase']['department']
    assert body['showcase']['department'] == sorted(
        [own_department.name, other_department.name], key=str.casefold
    )
    assert body['action_items']['status'] == [
        item.value for item in ActionStatus
    ]
    assert body['action_items']['deadline'] == {
        'from': '2026-08-14',
        'to': '2026-08-15',
    }
    assert body['action_items']['priority'] == ['П2', 'П4']
    assert [
        item['label'] for item in body['action_items']['assigned_user_id']
    ] == ['Анна Ярова', 'Борис Соболев']


async def test_filter_options_empty_data_keeps_static_values(
    client, session, users_by_role, auth_headers
):
    await session.execute(delete(ActionItem))
    await session.execute(delete(ShowcaseEvent))
    response = await client.get(
        '/filter-options', headers=auth_headers(users_by_role[UserRole.analyst])
    )

    assert response.status_code == 200
    assert response.json() == {
        'showcase': {
            'category': [],
            'region': [],
            'priority': ['П1', 'П2', 'П3', 'П4'],
            'competitor': [],
            'department': [],
            'media': [],
        },
        'action_items': {
            'status': ['open', 'in_progress', 'done'],
            'deadline': {'from': None, 'to': None},
            'priority': [],
            'assigned_user_id': [],
            'department_id': [],
        },
    }


@pytest.mark.parametrize(
    'role', [UserRole.viewer, UserRole.analyst, UserRole.admin]
)
async def test_filter_options_role_access_success(
    client, users_by_role, auth_headers, role
):
    response = await client.get(
        '/filter-options', headers=auth_headers(users_by_role[role])
    )
    assert response.status_code == 200


async def test_filter_options_rejects_anonymous_and_pending(
    client, users_by_role, auth_headers
):
    anonymous = await client.get('/filter-options')
    pending = await client.get(
        '/filter-options', headers=auth_headers(users_by_role[UserRole.pending])
    )
    assert anonymous.status_code == 401
    assert pending.status_code == 403


def test_filter_options_and_action_filters_have_exact_openapi_contract():
    schema = app.openapi()
    filter_operation = schema['paths']['/filter-options']['get']
    action_operation = schema['paths']['/action-items']['get']
    response_schema = filter_operation['responses']['200']['content'][
        'application/json'
    ]['schema']
    action_parameters = {
        parameter['name']: parameter
        for parameter in action_operation['parameters']
    }

    assert response_schema == {'$ref': '#/components/schemas/FilterOptionsRead'}
    assert {
        'deadline_from',
        'deadline_to',
        'priority',
    } <= action_parameters.keys()
    assert action_parameters['deadline_from']['schema']['anyOf'][0] == {
        'type': 'string',
        'format': 'date',
    }
    assert action_parameters['priority']['schema']['anyOf'][0] == {
        'type': 'string'
    }


async def test_viewer_scope_and_every_action_option_is_applicable(
    client, session, users_by_role, auth_headers
):
    (
        viewer,
        own_item,
        own_department,
        other_department,
    ) = await _create_option_data(session, users_by_role)
    viewer_headers = auth_headers(viewer)
    analyst_headers = auth_headers(users_by_role[UserRole.analyst])

    viewer_options = (
        await client.get('/filter-options', headers=viewer_headers)
    ).json()['action_items']
    analyst_options = (
        await client.get('/filter-options', headers=analyst_headers)
    ).json()['action_items']

    assert viewer_options['deadline'] == {
        'from': '2026-08-14',
        'to': '2026-08-14',
    }
    assert viewer_options['priority'] == ['П2']
    assert viewer_options['assigned_user_id'] == [
        {'value': users_by_role[UserRole.pending].id, 'label': 'Борис Соболев'}
    ]
    assert viewer_options['department_id'] == [
        {'value': own_department.id, 'label': own_department.name}
    ]
    assert {item['value'] for item in analyst_options['department_id']} >= {
        own_department.id,
        other_department.id,
    }

    filter_values = {
        'status': viewer_options['status'][0],
        'deadline_from': viewer_options['deadline']['from'],
        'deadline_to': viewer_options['deadline']['to'],
        'priority': viewer_options['priority'][0],
        'assigned_user_id': viewer_options['assigned_user_id'][0]['value'],
        'department_id': viewer_options['department_id'][0]['value'],
    }
    for key, value in filter_values.items():
        response = await client.get(
            '/action-items', headers=viewer_headers, params={key: value}
        )
        assert response.status_code == 200
        assert own_item.id in {item['id'] for item in response.json()}

    combined = await client.get(
        '/action-items', headers=viewer_headers, params=filter_values
    )
    assert {item['id'] for item in combined.json()} == {own_item.id}


async def test_media_option_filters_showcase_and_deadline_range_validation(
    client, session, users_by_role, auth_headers
):
    await _create_option_data(session, users_by_role)
    headers = auth_headers(users_by_role[UserRole.analyst])
    options = (await client.get('/filter-options', headers=headers)).json()

    media = options['showcase']['media'][0]
    showcase = await client.get(
        '/showcase', headers=headers, params={'media': media}
    )
    invalid_range = await client.get(
        '/action-items',
        headers=headers,
        params={'deadline_from': '2026-08-16', 'deadline_to': '2026-08-14'},
    )

    assert showcase.status_code == 200
    assert showcase.json()
    assert all(
        media.casefold() in item['media'].casefold() for item in showcase.json()
    )
    assert invalid_range.status_code == 422
