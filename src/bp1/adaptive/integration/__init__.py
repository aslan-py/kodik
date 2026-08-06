"""
Слой интеграции с BP-1 и внешними интерфейсами.

Содержит мосты и точки входа, связывающие adaptive-пакет с остальным
проектом:
- ``AdaptiveBridgeParser`` — мост к ``BaseParser`` BP-1.
- ``AdaptiveRunner`` — единая точка входа для сбора данных.
- ``MCPServer`` — MCP-сервер для управления сбором данных.
- ``SourceRegistrationService`` — регистрация нового источника по ссылке.
"""

from .sources import SourceRegistrationService

__all__ = ['SourceRegistrationService']
