"""Модели BP-2 (нормализация, дедупликация, фильтрация шума).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all. Enum'ы живут в
core.enums.
"""

from src.bp2.models import (
    BlackDomain,
    NormalizedItem,
    Region,
    StopWord,
    TopicLimit,
)

__all__ = [
    'BlackDomain',
    'NormalizedItem',
    'Region',
    'StopWord',
    'TopicLimit',
]
