import uuid
from datetime import datetime

from .constants import FILE_TIMESTAMP_FORMAT, REQUEST_ID_LENGTH


def generate_request_id() -> str:
    """Генерирует уникальный ID запроса."""
    return uuid.uuid4().hex[:REQUEST_ID_LENGTH]


def format_proxy_string(server: str, username: str | None = None) -> str:
    """Форматирует строку прокси для логирования (без пароля)."""
    if username:
        return f"{username}@{server}"
    return server


def format_timestamp() -> str:
    """Возвращает строку времени для именования файлов."""
    return datetime.now().strftime(FILE_TIMESTAMP_FORMAT)


_INN_WEIGHTS_10 = [2, 4, 10, 3, 5, 9, 4, 6, 8]
_INN_WEIGHTS_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
_INN_WEIGHTS_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]


def validate_inn(inn: str) -> bool:
    """Проверяет ИНН по контрольным суммам (10 или 12 цифр).

    Алгоритм: ГОСТ Р 34.10-2001 / Приказ ФНС от 09.06.2020 № ЕД-7-14/87@.

    Args:
        inn: Строка из цифр, длина 10 или 12.

    Returns:
        True, если ИНН валиден.

    Raises:
        ValueError: Если формат ИНН неверен (не цифры, неправильная длина).
    """
    if not inn.isdigit():
        raise ValueError(f"ИНН должен содержать только цифры: '{inn}'")

    digits = [int(c) for c in inn]
    length = len(digits)

    if length == 10:
        expected = sum(
            d * w for d, w in zip(digits[:9], _INN_WEIGHTS_10, strict=False)
        ) % 11 % 10
        if digits[9] != expected:
            raise ValueError(
                f"Неверная контрольная сумма ИНН: ожидалось {expected}, "
                f"получено {digits[9]}"
            )
        return True

    if length == 12:
        check_11 = sum(
            d * w for d, w in zip(digits[:10], _INN_WEIGHTS_11, strict=False)
        ) % 11 % 10
        if digits[10] != check_11:
            raise ValueError(
                f"Неверная 10-я контрольная сумма ИНН: ожидалось {check_11}, "
                f"получено {digits[10]}"
            )
        check_12 = sum(
            d * w for d, w in zip(
                digits[:11], _INN_WEIGHTS_12, strict=False
            )) % 11 % 10
        if digits[11] != check_12:
            raise ValueError(
                f"Неверная 11-я контрольная сумма ИНН: ожидалось {check_12}, "
                f"получено {digits[11]}"
            )
        return True

    raise ValueError(f"ИНН должен содержать 10 или 12 цифр, получено {length}")
