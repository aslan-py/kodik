"""Модели BP-1 (слой сбора данных).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all.
"""
from src.bp1.models import (
    Competitor,
    RawItem,
    RawItemStatus,
    SearchTask,
    Source,
    Trigger,
)

__all__ = [
    'Competitor',
    'RawItem',
    'RawItemStatus',
    'SearchTask',
    'Source',
    'Trigger',
]
