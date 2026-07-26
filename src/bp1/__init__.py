"""Модели BP-1 (слой сбора данных).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all. Enum'ы живут в
core.enums.
"""

from src.bp1.models import (
    Competitor,
    RawItem,
    SearchTask,
    Source,
    Trigger,
)

__all__ = [
    'Competitor',
    'RawItem',
    'SearchTask',
    'Source',
    'Trigger',
]
