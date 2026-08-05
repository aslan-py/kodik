"""Модели BP-4 (витрина данных под BI).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all.
"""

from src.bp4.models import ShowcaseEvent

__all__ = ['ShowcaseEvent']
