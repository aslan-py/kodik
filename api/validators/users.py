"""Переиспользуемые Pydantic-валидаторы для схем `api/schemas/users.py`.

Отдельно от DB-проверок уникальности (email/telegram_id) — те требуют
сессию и живут в `api/crud/users.py`
(`get_by_email`/`get_by_telegram_id`), здесь — чистая проверка формата
поля, без похода в БД.
"""

from typing import Annotated

from pydantic import AfterValidator

PASSWORD_MIN_LENGTH = 8


def validate_password(password: str) -> str:
    """Минимум 8 символов + хотя бы одна заглавная, строчная буква и цифра."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f'Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов'
        )
    if not any(char.isupper() for char in password):
        raise ValueError('Пароль должен содержать заглавную букву')
    if not any(char.islower() for char in password):
        raise ValueError('Пароль должен содержать строчную букву')
    if not any(char.isdigit() for char in password):
        raise ValueError('Пароль должен содержать цифру')
    return password


CustomPassword = Annotated[str, AfterValidator(validate_password)]
