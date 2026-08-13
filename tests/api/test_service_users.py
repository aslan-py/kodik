"""Тесты UserService: правка своих данных, смена роли."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.crud.users import UserCRUD
from api.schemas.users import UserRegister, UserRoleUpdate, UserUpdateMe
from api.service.users import UserService
from core.enums import UserRole
from src.bp3.models import Department
from src.bp5.models import User


async def _make_user(
    session, email='user@example.com', password='Passw0rd1', **kwargs
) -> User:
    crud = UserCRUD(session)
    data = UserRegister(email=email, password=password, **kwargs)
    return await crud.create(data)


class TestUpdateMe:
    async def test_no_changes_returns_current_user(self, session):
        user = await _make_user(session)

        updated = await UserService(session).update_me(user, UserUpdateMe())

        assert updated.email == user.email

    async def test_updates_full_name_without_current_password(self, session):
        user = await _make_user(session)

        updated = await UserService(session).update_me(
            user, UserUpdateMe(full_name='New Name')
        )

        assert updated.full_name == 'New Name'

    async def test_change_email_requires_current_password(self, session):
        user = await _make_user(session)

        with pytest.raises(HTTPException) as exc:
            await UserService(session).update_me(
                user, UserUpdateMe(email='new@example.com')
            )

        assert exc.value.status_code == 401

    async def test_change_email_with_correct_password_succeeds(self, session):
        user = await _make_user(session)

        updated = await UserService(session).update_me(
            user,
            UserUpdateMe(email='new@example.com', current_password='Passw0rd1'),
        )

        assert updated.email == 'new@example.com'

    async def test_change_password_wrong_current_password(self, session):
        user = await _make_user(session)

        with pytest.raises(HTTPException) as exc:
            await UserService(session).update_me(
                user,
                UserUpdateMe(
                    password='NewPassw0rd1', current_password='WrongPass1'
                ),
            )

        assert exc.value.status_code == 401

    async def test_email_conflict_with_other_user(self, session):
        await _make_user(session, email='taken@example.com')
        user = await _make_user(session, email='user2@example.com')

        with pytest.raises(HTTPException) as exc:
            await UserService(session).update_me(
                user,
                UserUpdateMe(
                    email='taken@example.com',
                    current_password='Passw0rd1',
                ),
            )

        assert exc.value.status_code == 409

    async def test_telegram_id_conflict_with_other_user(self, session):
        await _make_user(session, email='u1@example.com', telegram_id=111)
        user = await _make_user(session, email='u2@example.com')

        with pytest.raises(HTTPException) as exc:
            await UserService(session).update_me(
                user, UserUpdateMe(telegram_id=111)
            )

        assert exc.value.status_code == 409

    async def test_department_not_found(self, session):
        user = await _make_user(session)

        with pytest.raises(HTTPException) as exc:
            await UserService(session).update_me(
                user, UserUpdateMe(department_id=999_999)
            )

        assert exc.value.status_code == 404

    async def test_department_found_succeeds(self, session):
        department = Department(name=f'Отдел {uuid4()}')
        session.add(department)
        await session.flush()
        user = await _make_user(session)

        updated = await UserService(session).update_me(
            user, UserUpdateMe(department_id=department.id)
        )

        assert updated.department_id == department.id


class TestUpdateRole:
    async def test_updates_role(self, session):
        user = await _make_user(session)

        updated = await UserService(session).update_role(
            user.id, UserRoleUpdate(role=UserRole.viewer)
        )

        assert updated.role == UserRole.viewer

    async def test_unknown_user_not_found(self, session):
        with pytest.raises(HTTPException) as exc:
            await UserService(session).update_role(
                999_999, UserRoleUpdate(role=UserRole.viewer)
            )

        assert exc.value.status_code == 404


class TestGetUserById:
    async def test_returns_requested_user(self, session):
        user = await _make_user(session)

        result = await UserService(session).get_by_id(user.id)

        assert result.id == user.id

    async def test_unknown_user_not_found(self, session):
        with pytest.raises(HTTPException) as exc:
            await UserService(session).get_by_id(999_999)

        assert exc.value.status_code == 404
