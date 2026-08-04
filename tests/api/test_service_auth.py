"""Тесты AuthService: регистрация/логин/logout/сброс пароля.

send_email подменяется моком (autouse) — тесты не должны стучаться в
реальный SMTP, тот же приём, что и mock_send_email в
tests/bp5/test_crud.py.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.crud.users import UserCRUD
from api.schemas.users import (
    PasswordResetConfirm,
    PasswordResetRequest,
    UserLogin,
    UserRegister,
)
from api.security import hash_password, verify_password
from api.service.auth import AuthService


@pytest.fixture(autouse=True)
def mock_send_email(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr('api.service.auth.send_email', mock)
    return mock


async def _register(session, email='user@example.com', password='Passw0rd1'):
    return await AuthService(session).register(
        UserRegister(email=email, password=password)
    )


class TestRegister:
    async def test_creates_pending_user(self, session):
        user = await _register(session)
        assert user.role == 'pending'

    async def test_duplicate_email_conflicts(self, session):
        await _register(session)

        with pytest.raises(HTTPException) as exc:
            await _register(session)

        assert exc.value.status_code == 409


class TestLogin:
    async def test_success_returns_token(self, session):
        await _register(session)

        token = await AuthService(session).login(
            UserLogin(email='user@example.com', password='Passw0rd1')
        )

        assert token.access_token

    async def test_wrong_password_is_unauthorized(self, session):
        await _register(session)

        with pytest.raises(HTTPException) as exc:
            await AuthService(session).login(
                UserLogin(email='user@example.com', password='WrongPass1')
            )

        assert exc.value.status_code == 401


class TestLogout:
    async def test_returns_confirmation_with_email(self, session):
        user = await _register(session)
        db_user = await UserCRUD(session).get_by_email(user.email)

        message = await AuthService(session).logout(db_user)

        assert user.email in message.detail


class TestPasswordReset:
    async def test_request_for_existing_user_sends_email(
        self, session, mock_send_email
    ):
        await _register(session)

        await AuthService(session).request_password_reset(
            PasswordResetRequest(email='user@example.com')
        )

        mock_send_email.assert_awaited_once()

    async def test_request_for_unknown_email_stays_silent(
        self, session, mock_send_email
    ):
        message = await AuthService(session).request_password_reset(
            PasswordResetRequest(email='ghost@example.com')
        )

        mock_send_email.assert_not_awaited()
        assert message.detail  # generic-ответ всё равно приходит

    async def test_request_generic_message_same_for_known_and_unknown(
        self, session
    ):
        await _register(session)

        known = await AuthService(session).request_password_reset(
            PasswordResetRequest(email='user@example.com')
        )
        unknown = await AuthService(session).request_password_reset(
            PasswordResetRequest(email='ghost@example.com')
        )

        assert known.detail == unknown.detail

    async def test_confirm_success_changes_password(self, session):
        user = await _register(session)
        crud = UserCRUD(session)
        db_user = await crud.get_by_email(user.email)
        await crud.create_reset_code(db_user.id, hash_password('654321'))

        await AuthService(session).confirm_password_reset(
            PasswordResetConfirm(
                email=user.email,
                code='654321',
                new_password='NewPassw0rd1',
            )
        )

        refreshed = await crud.get_by_email(user.email)
        assert verify_password('NewPassw0rd1', refreshed.password_hash)

    async def test_confirm_wrong_code_increments_attempts(self, session):
        user = await _register(session)
        crud = UserCRUD(session)
        db_user = await crud.get_by_email(user.email)
        code_row = await crud.create_reset_code(
            db_user.id, hash_password('654321')
        )

        with pytest.raises(HTTPException) as exc:
            await AuthService(session).confirm_password_reset(
                PasswordResetConfirm(
                    email=user.email,
                    code='000000',
                    new_password='NewPassw0rd1',
                )
            )

        assert exc.value.status_code == 400
        assert code_row.attempts == 1

    async def test_confirm_expired_code_rejected(self, session):
        user = await _register(session)
        crud = UserCRUD(session)
        db_user = await crud.get_by_email(user.email)
        code_row = await crud.create_reset_code(
            db_user.id, hash_password('654321')
        )
        code_row.expires_at = datetime.now(UTC) - timedelta(minutes=1)

        with pytest.raises(HTTPException) as exc:
            await AuthService(session).confirm_password_reset(
                PasswordResetConfirm(
                    email=user.email,
                    code='654321',
                    new_password='NewPassw0rd1',
                )
            )

        assert exc.value.status_code == 400

    async def test_confirm_unknown_email_rejected_generic(self, session):
        with pytest.raises(HTTPException) as exc:
            await AuthService(session).confirm_password_reset(
                PasswordResetConfirm(
                    email='ghost@example.com',
                    code='123456',
                    new_password='NewPassw0rd1',
                )
            )

        assert exc.value.status_code == 400
