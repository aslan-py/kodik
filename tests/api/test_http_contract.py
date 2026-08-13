"""Базовый HTTP-контур для контрактных тестов FastAPI."""

import pytest

from api.main import app
from api.security import create_access_token
from core.enums import UserRole
from tests.api.http_manifest import (
    EDITOR,
    HTTP_MANIFEST,
    PUBLIC,
    VIEWER,
)

IMPLEMENTED_SUCCESS_SCENARIOS = {
    'register',
    'login',
    'logout',
    'reset-request',
    'reset-confirm',
    'current-user',
    'current-user-update',
    'users-list',
    'user-detail',
    'user-role',
    'showcase-list',
    'showcase-detail',
    'showcase-update',
    'action-item-create',
    'action-item-list',
    'action-item-detail',
    'action-item-update',
    'filter-options',
    'reference-list',
    'reference-create',
    'reference-detail',
    'reference-update',
    'reference-delete',
    'pipeline-list',
    'pipeline-detail',
}


async def test_asgi_client_reads_openapi_without_network_port(client):
    response = await client.get('/openapi.json')

    assert response.status_code == 200
    assert response.json()['openapi']


async def test_asgi_client_uses_current_test_session(
    client, session, department
):
    response = await client.get('/departments')

    assert response.status_code == 200
    assert any(item['id'] == department.id for item in response.json())
    assert session.in_transaction()


def test_manifest_matches_openapi_and_operation_ids_are_unique():
    schema = app.openapi()
    documented = {
        (method.upper(), path)
        for path, methods in schema['paths'].items()
        for method in methods
        if method in {'get', 'post', 'patch', 'put', 'delete'}
    }
    manifest = {(item.method, item.path) for item in HTTP_MANIFEST}
    operation_ids = [
        operation['operationId']
        for methods in schema['paths'].values()
        for operation in methods.values()
        if 'operationId' in operation
    ]

    assert len(HTTP_MANIFEST) == 92
    assert manifest == documented
    assert len(operation_ids) == len(set(operation_ids))


def test_every_manifest_operation_has_success_scenario_and_response_schema():
    schema = app.openapi()
    assert {
        item.scenario for item in HTTP_MANIFEST
    } <= IMPLEMENTED_SUCCESS_SCENARIOS
    for contract in HTTP_MANIFEST:
        operation = schema['paths'][contract.path][contract.method.lower()]
        response = operation['responses'][str(contract.success_status)]
        assert 'content' in response
        assert 'application/json' in response['content']
        assert 'schema' in response['content']['application/json']


@pytest.mark.parametrize('path', ['/openapi.json', '/docs', '/redoc', '/admin'])
async def test_documentation_and_admin_smoke_without_5xx(client, path):
    response = await client.get(path, follow_redirects=False)

    assert response.status_code < 500
    assert response.status_code in {200, 301, 302, 307, 308}


def _request_path(template: str) -> str:
    return (
        template.replace('{item_id}', '999999999')
        .replace('{showcase_id}', '999999999')
        .replace('{user_id}', '999999999')
    )


def _forbidden_role(access: str) -> UserRole | None:
    if access == VIEWER:
        return UserRole.pending
    if access == EDITOR:
        return UserRole.viewer
    return None


@pytest.mark.parametrize(
    'contract',
    [item for item in HTTP_MANIFEST if item.access != PUBLIC],
    ids=lambda item: f'{item.method} {item.path}',
)
async def test_protected_operations_reject_missing_and_invalid_tokens(
    client, contract
):
    path = _request_path(contract.path)
    without_token = await client.request(contract.method, path, json={})
    invalid_token = await client.request(
        contract.method,
        path,
        json={},
        headers={'Authorization': 'Bearer invalid-token'},
    )

    assert without_token.status_code == 401
    assert invalid_token.status_code == 401


@pytest.mark.parametrize(
    'contract',
    [
        item
        for item in HTTP_MANIFEST
        if _forbidden_role(item.access) is not None
    ],
    ids=lambda item: f'{item.method} {item.path}',
)
async def test_protected_operations_reject_forbidden_role(
    client, users_by_role, contract
):
    role = _forbidden_role(contract.access)
    assert role is not None
    token = create_access_token(str(users_by_role[role].id))

    response = await client.request(
        contract.method,
        _request_path(contract.path),
        json={},
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code in {403, 404}
