"""Модели BP-3 (LLM-категоризация, gold-слой).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all. Enum'ы живут в
core.enums.
"""

from src.bp3.models import CategorizedEvent, Category, Department

__all__ = ['CategorizedEvent', 'Category', 'Department']
