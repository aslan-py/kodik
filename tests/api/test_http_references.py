"""Параметризованный HTTP-контракт административных справочников."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from core.enums import UserRole


@dataclass(frozen=True)
class ReferenceCase:
    path: str
    create: dict
    update: dict
    changed_field: str
    search: str | None = None


def _cases() -> list[ReferenceCase]:
    marker = uuid4().hex
    return [
        ReferenceCase(
            '/competitors',
            {'name': f'Competitor {marker}'},
            {'name': f'Competitor updated {marker}'},
            'name',
            marker,
        ),
        ReferenceCase(
            '/sources',
            {'name': f'Source {marker}'},
            {'name': f'Source updated {marker}'},
            'name',
            marker,
        ),
        ReferenceCase(
            '/triggers',
            {'keyword': f'Trigger {marker}'},
            {'keyword': f'Trigger updated {marker}'},
            'keyword',
            marker,
        ),
        ReferenceCase(
            '/black-domains',
            {'domain': f'{marker}.example.com'},
            {'reason': 'HTTP verified'},
            'reason',
            marker,
        ),
        ReferenceCase(
            '/stop-words',
            {'phrase': f'Phrase {marker}', 'type': 'stop_word'},
            {'note': 'HTTP verified'},
            'note',
            marker,
        ),
        ReferenceCase(
            '/topic-limits',
            {'scope': 'media', 'max_count': 987654, 'window': 'run'},
            {'note': f'HTTP {marker}'},
            'note',
        ),
        ReferenceCase(
            '/categories',
            {'name': f'Category {marker}'},
            {'note': 'HTTP verified'},
            'note',
            marker,
        ),
        ReferenceCase(
            '/departments',
            {'name': f'Department {marker}'},
            {'note': 'HTTP verified'},
            'note',
            marker,
        ),
        ReferenceCase(
            '/event-types',
            {'name': f'Event {marker}', 'keywords': [marker]},
            {'keywords': [marker, 'updated']},
            'keywords',
            marker,
        ),
        ReferenceCase(
            '/channels',
            {'name': f'Channel {marker}'},
            {'name': f'Channel updated {marker}'},
            'name',
            marker,
        ),
    ]


@pytest.mark.parametrize('case', _cases(), ids=lambda case: case.path)
async def test_reference_crud_list_detail_update_delete(
    client, users_by_role, auth_headers, case
):
    headers = auth_headers(users_by_role[UserRole.admin])
    created = await client.post(case.path, headers=headers, json=case.create)
    assert created.status_code == 201, created.text
    item_id = created.json()['id']
    params = {'q': case.search} if case.search else {}
    listed = await client.get(case.path, headers=headers, params=params)
    detail = await client.get(f'{case.path}/{item_id}', headers=headers)
    updated = await client.patch(
        f'{case.path}/{item_id}', headers=headers, json=case.update
    )
    missing = await client.get(f'{case.path}/999999999', headers=headers)
    deleted = await client.delete(f'{case.path}/{item_id}', headers=headers)

    assert listed.status_code == 200
    assert item_id in {item['id'] for item in listed.json()}
    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()[case.changed_field] == case.update[case.changed_field]
    assert missing.status_code == 404
    assert deleted.status_code == 200
    assert deleted.json()['is_active'] is False


@pytest.mark.parametrize('case', _cases(), ids=lambda case: case.path)
async def test_reference_duplicate_returns_409(
    client, users_by_role, auth_headers, case
):
    if case.path == '/topic-limits':
        pytest.skip('topic_limit не имеет ограничения уникальности')
    headers = auth_headers(users_by_role[UserRole.admin])
    first = await client.post(case.path, headers=headers, json=case.create)
    assert first.status_code == 201, first.text

    duplicate = await client.post(case.path, headers=headers, json=case.create)

    assert duplicate.status_code == 409


async def test_department_reads_are_public_and_region_has_no_delete(
    client, users_by_role, auth_headers
):
    headers = auth_headers(users_by_role[UserRole.admin])
    marker = uuid4().hex
    department = await client.post(
        '/departments',
        headers=headers,
        json={'name': f'Public department {marker}'},
    )
    region = await client.post(
        '/regions',
        headers=headers,
        json={'name_display': f'Region {marker}', 'name_aliases': [marker]},
    )

    assert (await client.get('/departments')).status_code == 200
    assert (
        await client.get(f'/departments/{department.json()["id"]}')
    ).status_code == 200
    assert region.status_code == 201
    region_id = region.json()['id']
    assert (
        await client.get('/regions', headers=headers, params={'q': marker})
    ).status_code == 200
    assert (
        await client.get(f'/regions/{region_id}', headers=headers)
    ).status_code == 200
    assert (
        await client.patch(
            f'/regions/{region_id}',
            headers=headers,
            json={'macro_region': 'HTTP'},
        )
    ).status_code == 200
    assert (
        await client.delete(f'/regions/{region_id}', headers=headers)
    ).status_code == 405


async def test_routing_rule_crud_and_filters(
    client, users_by_role, auth_headers
):
    headers = auth_headers(users_by_role[UserRole.admin])
    marker = uuid4().hex
    event_type = await client.post(
        '/event-types',
        headers=headers,
        json={'name': f'Routing event {marker}', 'keywords': [marker]},
    )
    channel = await client.post(
        '/channels', headers=headers, json={'name': f'Routing channel {marker}'}
    )
    payload = {
        'event_type_id': event_type.json()['id'],
        'priority': 'p1',
        'user_id': users_by_role[UserRole.viewer].id,
        'channel_id': channel.json()['id'],
        'mode': 'instant',
    }
    created = await client.post('/routing-rules', headers=headers, json=payload)
    assert created.status_code == 201, created.text
    item_id = created.json()['id']
    listed = await client.get('/routing-rules', headers=headers)
    detail = await client.get(f'/routing-rules/{item_id}', headers=headers)
    updated = await client.patch(
        f'/routing-rules/{item_id}', headers=headers, json={'mode': 'digest'}
    )
    deleted = await client.delete(f'/routing-rules/{item_id}', headers=headers)

    assert item_id in {item['id'] for item in listed.json()}
    assert detail.status_code == 200
    assert updated.json()['mode'] == 'digest'
    assert deleted.json()['is_active'] is False
