"""Модели BP-5 (детектор событий, алертинг, маршрутизация).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all. Enum'ы живут в
core.enums.
"""

from src.bp5.models import Alert, Channel, EventType, RoutingRule, User

__all__ = ['Alert', 'Channel', 'EventType', 'RoutingRule', 'User']
