import random

from .constants import (
    HUMAN_DELAY_RANGE_SEC,
    RANDOM_DELAY_RANGE_SEC,
    USER_AGENTS,
)

# Переэкспорт для обратной совместимости


def get_random_user_agent() -> str:
    """Возвращает случайный User-Agent из пула."""
    return random.choice(USER_AGENTS)


def get_random_delay() -> float:
    """Возвращает случайную задержку из диапазона RANDOM_DELAY_RANGE_SEC."""
    return random.uniform(*RANDOM_DELAY_RANGE_SEC)


def get_human_delay() -> float:
    """Возвращает случайную задержку для имитации поведения человека."""
    return random.uniform(*HUMAN_DELAY_RANGE_SEC)
