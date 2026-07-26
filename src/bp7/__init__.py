"""Модели BP-7 (агент расширения источников).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all. Enum'ы живут в
core.enums.
"""

from src.bp7.models import SourceCandidate

__all__ = ['SourceCandidate']
