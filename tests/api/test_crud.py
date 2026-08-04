"""Тесты UserCRUD: правка своих данных, коды сброса пароля.

Сессия из conftest не коммитит — данные откатываются после каждого теста
(commit подменён no-op в tests/api/conftest.py, CRUD-методы делают только
flush, так что состояние видно внутри транзакции).
"""

from api.crud.users import MAX_RESET_ATTEMPTS, UserCRUD
from api.schemas.users import UserRegister
from api.security import hash_password, verify_password
from src.bp5.models import User


async def _make_user(session, email='user@example.com', **kwargs) -> User:
    crud = UserCRUD(session)
    data = UserRegister(email=email, password='Passw0rd1', **kwargs)
    return await crud.create(data)


class TestUpdateSelf:
    async def test_updates_only_passed_fields(self, session):
        crud = UserCRUD(session)
        user = await _make_user(session, full_name='Old Name')

        updated = await crud.update_self(user, {'full_name': 'New Name'})

        assert updated.full_name == 'New Name'
        assert updated.email == 'user@example.com'

    async def test_hashes_password(self, session):
        crud = UserCRUD(session)
        user = await _make_user(session)
        old_hash = user.password_hash

        updated = await crud.update_self(user, {'password': 'NewPassw0rd1'})

        assert updated.password_hash != old_hash
        assert verify_password('NewPassw0rd1', updated.password_hash)


class TestPasswordResetCode:
    async def test_create_reset_code_replaces_previous(self, session):
        crud = UserCRUD(session)
        user = await _make_user(session)

        first = await crud.create_reset_code(user.id, hash_password('111111'))
        second = await crud.create_reset_code(user.id, hash_password('222222'))

        active = await crud.get_active_reset_code(user.id)
        assert active.id == second.id
        assert active.id != first.id

    async def test_mark_code_used_deactivates(self, session):
        crud = UserCRUD(session)
        user = await _make_user(session)
        code = await crud.create_reset_code(user.id, hash_password('123456'))

        await crud.mark_code_used(code)

        assert await crud.get_active_reset_code(user.id) is None

    async def test_register_failed_attempt_increments(self, session):
        crud = UserCRUD(session)
        user = await _make_user(session)
        code = await crud.create_reset_code(user.id, hash_password('123456'))

        await crud.register_failed_attempt(code)

        assert code.attempts == 1
        assert code.used_at is None

    async def test_register_failed_attempt_exhausts_after_max(self, session):
        crud = UserCRUD(session)
        user = await _make_user(session)
        code = await crud.create_reset_code(user.id, hash_password('123456'))

        for _ in range(MAX_RESET_ATTEMPTS):
            await crud.register_failed_attempt(code)

        assert code.used_at is not None
        assert await crud.get_active_reset_code(user.id) is None
