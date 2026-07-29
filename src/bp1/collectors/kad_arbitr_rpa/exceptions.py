class ParsingError(Exception):
    """Базовое исключение пакета kad_arbitr_rpa."""


class ElementNotFoundError(ParsingError):
    """Элемент не найден на странице."""


class TimeoutExceededError(ParsingError):
    """Превышено время ожидания."""


class ProxyError(ParsingError):
    """Ошибка подключения к прокси."""
