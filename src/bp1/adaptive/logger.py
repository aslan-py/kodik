"""Настройка логирования для bp1.adaptive.

Внимание: этот модуль НЕ создаёт хендлеры логирования.
Конфигурация логирования (basicConfig) выполняется в точке входа
(cli.py, runner.py и т.д.), чтобы избежать дублирования сообщений
из-за множественных хендлеров и propagation.
"""

from __future__ import annotations

import logging
import uuid


def get_logger(name: str = 'bp1_adaptive') -> logging.Logger:
    """Получить логгер.

    Функция не создаёт хендлеры — это ответственность точки входа.
    Используется как тонкая обёртка над logging.getLogger() для
    совместимости с существующим кодом.

    Args:
        name: Имя логгера (по умолчанию 'bp1_adaptive').

    Returns:
        logging.Logger: Экземпляр логгера.
    """
    return logging.getLogger(name)


def new_trace_id() -> str:
    """Генерирует новый trace_id."""
    return uuid.uuid4().hex
