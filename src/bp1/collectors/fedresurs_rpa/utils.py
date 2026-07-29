"""Вспомогательные функции для fedresurs_rpa."""

from datetime import datetime

from .models import ProxyConfig


def format_proxy_string(proxy: ProxyConfig | None) -> str | None:
    """Форматировать конфигурацию прокси в строку."""
    if proxy is None:
        return None
    if proxy.username and proxy.password:
        return f'{proxy.server} ({proxy.username}:***)'
    return proxy.server


def validate_inn(inn: str) -> None:
    """Проверить российский ИНН (10 или 12 цифр).

    Args:
        inn: Строка ИНН для проверки.

    Raises:
        ValueError: Если ИНН невалиден (не цифры, неверная длина,
                    плохая контрольная сумма).
    """
    if not inn.isdigit():
        raise ValueError('ИНН должен содержать только цифры')

    if len(inn) not in (10, 12):
        raise ValueError('ИНН должен содержать 10 или 12 цифр')

    if len(inn) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum = sum(int(inn[i]) * weights[i] for i in range(9)) % 11 % 10
        if checksum != int(inn[9]):
            raise ValueError('Неверная контрольная сумма ИНН')
    else:
        weights1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        weights2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        check1 = sum(int(inn[i]) * weights1[i] for i in range(10)) % 11 % 10
        check2 = sum(int(inn[i]) * weights2[i] for i in range(11)) % 11 % 10
        if check1 != int(inn[10]) or check2 != int(inn[11]):
            raise ValueError('Неверная контрольная сумма ИНН')


def generate_filename(
    name: str,
    inn: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """Сгенерировать имя файла для сохранённого HTML.

    Args:
        name: Название компании.
        inn: Опциональный ИНН для имени файла.
        timestamp: Опциональная метка времени (текущее время, если None).

    Returns:
        Строка с именем файла.
    """
    if timestamp is None:
        timestamp = datetime.now()

    date_str = timestamp.strftime('%Y%m%d_%H%M%S')

    if inn:
        safe_name = inn
    else:
        safe_name = ''.join(c if c.isalnum() else '_' for c in name)[:50]

    return f'fedresurs_{safe_name}_{date_str}.html'
