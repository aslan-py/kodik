"""Декларативный реестр опубликованных HTTP-операций приложения."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EndpointContract:
    method: str
    path: str
    access: str
    success_status: int
    scenario: str


PUBLIC = 'public'
AUTHENTICATED = 'authenticated'
VIEWER = 'viewer'
EDITOR = 'editor'


def _operations(
    prefix: str,
    *,
    read_access: str = EDITOR,
    writable: bool = True,
    soft_delete: bool = True,
) -> tuple[EndpointContract, ...]:
    contracts = [
        EndpointContract('GET', prefix, read_access, 200, 'reference-list'),
        EndpointContract('POST', prefix, EDITOR, 201, 'reference-create'),
        EndpointContract(
            'GET', f'{prefix}/{{item_id}}', read_access, 200, 'reference-detail'
        ),
        EndpointContract(
            'PATCH', f'{prefix}/{{item_id}}', EDITOR, 200, 'reference-update'
        ),
    ]
    if not writable:
        return tuple(item for item in contracts if item.method == 'GET')
    if soft_delete:
        contracts.append(
            EndpointContract(
                'DELETE',
                f'{prefix}/{{item_id}}',
                EDITOR,
                200,
                'reference-delete',
            )
        )
    return tuple(contracts)


HTTP_MANIFEST = (
    EndpointContract('POST', '/auth/register', PUBLIC, 201, 'register'),
    EndpointContract('POST', '/auth/login', PUBLIC, 200, 'login'),
    EndpointContract('POST', '/auth/logout', AUTHENTICATED, 200, 'logout'),
    EndpointContract(
        'POST', '/auth/password-reset/request', PUBLIC, 200, 'reset-request'
    ),
    EndpointContract(
        'POST', '/auth/password-reset/confirm', PUBLIC, 200, 'reset-confirm'
    ),
    EndpointContract('GET', '/users/me', AUTHENTICATED, 200, 'current-user'),
    EndpointContract(
        'PATCH', '/users/me', AUTHENTICATED, 200, 'current-user-update'
    ),
    EndpointContract('GET', '/users', EDITOR, 200, 'users-list'),
    EndpointContract(
        'PATCH', '/users/{user_id}/role', EDITOR, 200, 'user-role'
    ),
    EndpointContract('GET', '/showcase', VIEWER, 200, 'showcase-list'),
    EndpointContract(
        'GET', '/showcase/{showcase_id}', VIEWER, 200, 'showcase-detail'
    ),
    EndpointContract(
        'PATCH', '/showcase/{showcase_id}', EDITOR, 200, 'showcase-update'
    ),
    EndpointContract(
        'POST', '/action-items', EDITOR, 201, 'action-item-create'
    ),
    EndpointContract('GET', '/action-items', VIEWER, 200, 'action-item-list'),
    EndpointContract('GET', '/filter-options', VIEWER, 200, 'filter-options'),
    EndpointContract(
        'GET', '/action-items/{item_id}', VIEWER, 200, 'action-item-detail'
    ),
    EndpointContract(
        'PATCH', '/action-items/{item_id}', VIEWER, 200, 'action-item-update'
    ),
    *_operations('/competitors'),
    *_operations('/sources'),
    *_operations('/triggers'),
    *_operations('/search-tasks'),
    *_operations('/regions', soft_delete=False),
    *_operations('/black-domains'),
    *_operations('/stop-words'),
    *_operations('/topic-limits'),
    *_operations('/categories'),
    *_operations('/departments', read_access=PUBLIC),
    *_operations('/event-types'),
    *_operations('/channels'),
    *_operations('/routing-rules'),
    *(
        EndpointContract('GET', prefix, EDITOR, 200, 'pipeline-list')
        for prefix in (
            '/raw-items',
            '/normalized-items',
            '/categorized-events',
            '/alerts',
            '/source-candidates',
        )
    ),
    *(
        EndpointContract(
            'GET', f'{prefix}/{{item_id}}', EDITOR, 200, 'pipeline-detail'
        )
        for prefix in (
            '/raw-items',
            '/normalized-items',
            '/categorized-events',
            '/alerts',
            '/source-candidates',
        )
    ),
)
