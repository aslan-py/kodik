import logging


def get_logger(name: str = 'kad_arbitr_rpa') -> logging.Logger:
    """Получить логгер.

    Функция не создаёт хендлеры — это ответственность точки входа.
    Используется как тонкая обёртка над logging.getLogger() для
    совместимости с существующим кодом.

    Args:
        name: Имя логгера (по умолчанию 'kad_arbitr_rpa').

    Returns:
        logging.Logger: Экземпляр логгера.
    """
    return logging.getLogger(name)
