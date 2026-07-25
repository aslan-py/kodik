"""Модели BP-2 (нормализация, дедупликация, фильтрация шума).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all.
"""

from src.bp2.models import (
    BlackDomain,
    LimitScope,
    LimitWindow,
    NormalizedItem,
    NormStatus,
    Region,
    RejectReason,
    StopType,
    StopWord,
    TopicLimit,
)

__all__ = [
    'BlackDomain',
    'LimitScope',
    'LimitWindow',
    'NormStatus',
    'NormalizedItem',
    'Region',
    'RejectReason',
    'StopType',
    'StopWord',
    'TopicLimit',
]
