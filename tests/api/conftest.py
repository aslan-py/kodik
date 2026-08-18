"""Общие фикстуры API-тестов.

`session` берётся из tests/conftest.py (без commit, откат после теста).
Сервисы api/service/* сами вызывают session.commit() (не только flush,
как CRUD в src/bp*/crud.py) — если дать этому commit'у реально сработать
в тесте, данные утекут в БД мимо отката фикстуры. Подменяем commit на
no-op: CRUD-методы всё равно делают flush() перед ним, так что изменения
видны в транзакции, а откат в конце теста (tests/conftest.py::session)
работает как обычно, потому что до реальной БД commit не доходит — тот же
принцип изоляции, что и в tests/bp5/test_crud.py, где run_bp5() (с
реальным commit) в тестах никогда не вызывается напрямую.
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from api.dependencies import get_async_session
from api.main import app
from api.security import create_access_token, hash_password
from core.enums import UserRole
from src.bp3.models import Department
from src.bp5.models import User


@pytest.fixture(autouse=True)
def no_commit(session, monkeypatch):
    monkeypatch.setattr(session, 'commit', AsyncMock())


@pytest.fixture
async def client(session) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP-клиент приложения без сетевого порта и со сессией текущего теста."""

    async def get_test_session() -> AsyncIterator:
        yield session

    app.dependency_overrides[get_async_session] = get_test_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url='http://testserver'
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_external_api_boundaries(monkeypatch):
    """Запрещает API-тестам отправлять письма во внешнюю сеть."""
    send_email = AsyncMock()
    monkeypatch.setattr('api.service.auth.send_email', send_email)
    return send_email


@pytest.fixture
async def department(session) -> Department:
    item = Department(name=f'__api-test-department-{uuid4().hex}__')
    session.add(item)
    await session.flush()
    return item


@pytest.fixture
async def users_by_role(session, department) -> dict[UserRole, User]:
    """Уникальные пользователи всех ролей для HTTP-ролевой матрицы."""
    users = {}
    for role in UserRole:
        user = User(
            full_name=f'API {role.value}',
            email=f'api-{role.value}-{uuid4().hex}@example.com',
            password_hash=hash_password('Password123'),
            department_id=department.id,
            role=role,
        )
        session.add(user)
        users[role] = user
    await session.flush()
    return users


@pytest.fixture
def auth_headers():
    def make(user: User) -> dict[str, str]:
        return {'Authorization': f'Bearer {create_access_token(str(user.id))}'}

    return make
