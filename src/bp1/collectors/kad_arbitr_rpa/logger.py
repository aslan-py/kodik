import logging

from .constants import LOG_FORMAT, LOG_LEVEL


def get_logger(name: str = "kad_arbitr_rpa") -> logging.Logger:
    """Создаёт и возвращает логгер с стандартным форматом."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, LOG_LEVEL))
    return logger
