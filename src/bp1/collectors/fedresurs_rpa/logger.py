"""Настройка логирования для fedresurs_rpa.

Внимание: этот модуль НЕ создаёт хендлеры логирования.
Конфигурация логирования (basicConfig) выполняется в точке входа
(test_parser.py, run_pipeline.py и т.д.), чтобы избежать дублирования
сообщений из-за множественных хендлеров и propagation.
"""

import logging


def get_logger(name: str = 'fedresurs_rpa') -> logging.Logger:
    """Получить логгер.

    Функция не создаёт хендлеры — это ответственность точки входа.
    Используется как тонкая обёртка над logging.getLogger() для
    совместимости с существующим кодом.

    Args:
        name: Имя логгера (по умолчанию 'fedresurs_rpa').

    Returns:
        logging.Logger: Экземпляр логгера.
    """
    return logging.getLogger(name)
