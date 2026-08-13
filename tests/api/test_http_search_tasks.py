"""HTTP-контракт матрицы задач сбора."""

from uuid import uuid4

from core.enums import UserRole


async def test_search_task_crud_filters_conflict_and_soft_delete(
    client, users_by_role, auth_headers
):
    headers = auth_headers(users_by_role[UserRole.analyst])
    marker = uuid4().hex
    competitor = await client.post(
        '/competitors',
        headers=headers,
        json={'name': f'HTTP competitor {marker}'},
    )
    source = await client.post(
        '/sources', headers=headers, json={'name': f'HTTP source {marker}'}
    )
    payload = {
        'competitor_id': competitor.json()['id'],
        'source_id': source.json()['id'],
    }
    created = await client.post('/search-tasks', headers=headers, json=payload)
    item_id = created.json()['id']
    trigger = await client.post(
        '/triggers', headers=headers, json={'keyword': f'HTTP trigger {marker}'}
    )
    listed = await client.get('/search-tasks', headers=headers, params=payload)
    detail = await client.get(f'/search-tasks/{item_id}', headers=headers)
    updated = await client.patch(
        f'/search-tasks/{item_id}',
        headers=headers,
        json={'trigger_id': trigger.json()['id']},
    )
    deleted = await client.delete(f'/search-tasks/{item_id}', headers=headers)

    assert competitor.status_code == source.status_code == 201
    assert created.status_code == 201
    assert item_id in {item['id'] for item in listed.json()}
    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()['trigger_id'] == trigger.json()['id']
    assert deleted.status_code == 200
    assert deleted.json()['is_active'] is False


async def test_search_task_duplicate_returns_conflict(
    client, users_by_role, auth_headers
):
    headers = auth_headers(users_by_role[UserRole.analyst])
    marker = uuid4().hex
    competitor = await client.post(
        '/competitors',
        headers=headers,
        json={'name': f'HTTP competitor {marker}'},
    )
    source = await client.post(
        '/sources', headers=headers, json={'name': f'HTTP source {marker}'}
    )
    payload = {
        'competitor_id': competitor.json()['id'],
        'source_id': source.json()['id'],
    }
    assert (
        await client.post('/search-tasks', headers=headers, json=payload)
    ).status_code == 201

    duplicate = await client.post(
        '/search-tasks', headers=headers, json=payload
    )

    assert duplicate.status_code == 409
