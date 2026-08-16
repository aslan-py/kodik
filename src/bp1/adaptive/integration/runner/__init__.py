"""AdaptiveRunner — единая точка входа для адаптивного сбора данных.

Реэкспортирует публичный API пакета:

- ``core`` — класс ``AdaptiveRunner`` и ``check_strategy_chain``.
- ``probing`` — резолвинг поискового URL (``_ProbingMixin``).
- ``batch`` — пакетный/конкурентный запуск задач (``_BatchMixin``).
"""

from .core import AdaptiveRunner, check_strategy_chain

__all__ = [
    'AdaptiveRunner',
    'check_strategy_chain',
]
