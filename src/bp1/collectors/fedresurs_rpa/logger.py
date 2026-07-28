"""Настройка логирования для fedresurs_rpa."""

import logging


def get_logger(name: str = 'fedresurs_rpa') -> logging.Logger:
    """Получить настроенный логгер."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
