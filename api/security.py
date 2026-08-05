"""Пароли и JWT: хэш/проверка пароля, выдача и разбор access-токена.

bcrypt через passlib — хэш пароля пользователя (User.password_hash).
python-jose — подпись/проверка JWT (HS256, секрет — settings.jwt_secret_key).

bearer_scheme (HTTPBearer) — откуда FastAPI берёт токен из запроса
(заголовок `Authorization: Bearer <token>`). Раньше здесь стоял
`OAuth2PasswordBearer(tokenUrl='auth/login')` — он декларирует в OpenAPI
полноценный OAuth2-password-flow, из-за чего кнопка Authorize в Swagger
показывает поля username/password и сама пытается сделать form-data POST
на `/auth/login` — а он принимает JSON, не form-data, так что этот
диалог в принципе не мог сработать. `HTTPBearer` — просто «есть токен,
положи его как есть в заголовок» без своего flow: Authorize показывает
одно поле Value, токен туда вставляется вручную (как и раньше).
`auto_error=False` — чтобы при отсутствии заголовка 401 кидал именно наш
`get_current_user` (см. `api/dependencies.py`) с нашим текстом, а не
FastAPI сам по себе с `403 Not authenticated`.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings

ALGORITHM = 'HS256'

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str) -> str:
    """Выдать JWT: sub=subject (User.id как строка), exp по settings."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {'sub': subject, 'exp': expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Разобрать JWT. None при невалидной подписи/истёкшем токене."""
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[ALGORITHM]
        )
    except JWTError:
        return None
