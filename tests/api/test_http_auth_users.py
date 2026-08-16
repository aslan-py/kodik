"""HTTP-контракт аутентификации и пользователей."""

from uuid import uuid4

from core.enums import UserRole


async def test_register_login_logout_and_current_user(client):
    email = f'http-register-{uuid4().hex}@example.com'
    password = 'Password123'
    registered = await client.post(
        '/auth/register', json={'email': email, 'password': password}
    )
    login = await client.post(
        '/auth/login', json={'email': email, 'password': password}
    )

    assert registered.status_code == 201
    assert registered.json()['role'] == UserRole.pending
    assert login.status_code == 200
    headers = {'Authorization': f'Bearer {login.json()["access_token"]}'}
    assert (await client.get('/users/me', headers=headers)).status_code == 200
    assert (
        await client.post('/auth/logout', headers=headers)
    ).status_code == 200
    assert (
        await client.post(
            '/auth/login', json={'email': email, 'password': 'bad'}
        )
    ).status_code == 401


async def test_inactive_user_cannot_use_valid_jwt(
    client, users_by_role, auth_headers
):
    user = users_by_role[UserRole.pending]
    user.is_active = False

    response = await client.get('/users/me', headers=auth_headers(user))

    assert response.status_code == 401


async def test_password_reset_request_is_generic_and_sends_only_for_known_email(
    client, users_by_role, mock_external_api_boundaries, monkeypatch
):
    user = users_by_role[UserRole.viewer]
    monkeypatch.setattr(
        'api.service.auth.generate_reset_code', lambda: '123456'
    )
    known = await client.post(
        '/auth/password-reset/request', json={'email': user.email}
    )
    unknown = await client.post(
        '/auth/password-reset/request',
        json={'email': f'unknown-{uuid4().hex}@example.com'},
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    mock_external_api_boundaries.assert_awaited_once()


async def test_password_reset_confirm_changes_password(
    client, users_by_role, monkeypatch
):
    user = users_by_role[UserRole.viewer]
    monkeypatch.setattr(
        'api.service.auth.generate_reset_code', lambda: '123456'
    )
    await client.post(
        '/auth/password-reset/request', json={'email': user.email}
    )

    response = await client.post(
        '/auth/password-reset/confirm',
        json={
            'email': user.email,
            'code': '123456',
            'new_password': 'NewPassword123',
        },
    )

    assert response.status_code == 200
    login = await client.post(
        '/auth/login', json={'email': user.email, 'password': 'NewPassword123'}
    )
    assert login.status_code == 200


async def test_update_me_enforces_password_and_forbids_privilege_change(
    client, users_by_role, auth_headers
):
    user = users_by_role[UserRole.viewer]
    headers = auth_headers(user)

    assert (
        await client.patch('/users/me', headers=headers, json={'role': 'admin'})
    ).status_code == 422
    assert (
        await client.patch(
            '/users/me', headers=headers, json={'is_active': False}
        )
    ).status_code == 422
    assert (
        await client.patch(
            '/users/me',
            headers=headers,
            json={'email': f'new-{uuid4().hex}@example.com'},
        )
    ).status_code == 401
    updated = await client.patch(
        '/users/me',
        headers=headers,
        json={'full_name': 'Updated API User'},
    )
    assert updated.status_code == 200
    assert updated.json()['full_name'] == 'Updated API User'


async def test_update_me_changes_sensitive_fields_and_rejects_email_conflict(
    client, users_by_role, auth_headers
):
    user = users_by_role[UserRole.viewer]
    other = users_by_role[UserRole.analyst]
    headers = auth_headers(user)

    conflict = await client.patch(
        '/users/me',
        headers=headers,
        json={'email': other.email, 'current_password': 'Password123'},
    )
    changed = await client.patch(
        '/users/me',
        headers=headers,
        json={
            'password': 'ChangedPassword123',
            'current_password': 'Password123',
        },
    )

    assert conflict.status_code == 409
    assert changed.status_code == 200
    login = await client.post(
        '/auth/login',
        json={'email': user.email, 'password': 'ChangedPassword123'},
    )
    assert login.status_code == 200


async def test_users_list_filter_and_role_update(
    client, users_by_role, auth_headers
):
    editor = users_by_role[UserRole.admin]
    pending = users_by_role[UserRole.pending]
    headers = auth_headers(editor)
    listed = await client.get(
        '/users', params={'email': pending.email}, headers=headers
    )
    updated = await client.patch(
        f'/users/{pending.id}/role', headers=headers, json={'role': 'viewer'}
    )

    assert listed.status_code == 200
    assert [item['id'] for item in listed.json()] == [pending.id]
    assert updated.status_code == 200
    assert updated.json()['role'] == 'viewer'
    assert (
        await client.patch(
            '/users/999999999/role', headers=headers, json={'role': 'viewer'}
        )
    ).status_code == 404


async def test_admin_update_changes_department_and_activity(
    client, session, users_by_role, auth_headers
):
    from src.bp3.models import Department

    target = users_by_role[UserRole.pending]
    department = Department(name=f'Отдел {uuid4().hex}')
    session.add(department)
    await session.flush()
    response = await client.patch(
        f'/users/{target.id}/role',
        headers=auth_headers(users_by_role[UserRole.admin]),
        json={'department_id': department.id, 'is_active': False},
    )

    assert response.status_code == 200
    assert response.json()['department_id'] == department.id
    assert response.json()['is_active'] is False
    assert response.json()['role'] == UserRole.pending

    missing = await client.patch(
        f'/users/{target.id}/role',
        headers=auth_headers(users_by_role[UserRole.admin]),
        json={'department_id': 999_999},
    )
    assert missing.status_code == 404

    unauthenticated = await client.patch(
        f'/users/{target.id}/role', json={'is_active': False}
    )
    forbidden = await client.patch(
        f'/users/{target.id}/role',
        headers=auth_headers(users_by_role[UserRole.viewer]),
        json={'is_active': False},
    )
    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403


async def test_user_by_id_requires_editor_role_and_returns_requested_user(
    client, users_by_role, auth_headers
):
    target = users_by_role[UserRole.pending]
    admin_headers = auth_headers(users_by_role[UserRole.admin])

    found = await client.get(f'/users/{target.id}', headers=admin_headers)
    missing = await client.get('/users/999999999', headers=admin_headers)
    unauthenticated = await client.get(f'/users/{target.id}')
    forbidden = await client.get(
        f'/users/{target.id}',
        headers=auth_headers(users_by_role[UserRole.viewer]),
    )

    assert found.status_code == 200
    assert found.json()['id'] == target.id
    assert missing.status_code == 404
    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
