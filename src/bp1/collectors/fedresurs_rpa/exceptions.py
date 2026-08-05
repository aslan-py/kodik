"""Пользовательские исключения пакета fedresurs_rpa."""


class FedresursRPAException(Exception):
    """Базовое исключение пакета fedresurs_rpa."""

    pass


class BrowserStartError(FedresursRPAException):
    """Ошибка запуска браузера."""

    pass


class PageLoadError(FedresursRPAException):
    """Ошибка загрузки страницы."""

    pass


class ElementNotFoundError(FedresursRPAException):
    """Элемент не найден на странице."""

    pass


class ProxyError(FedresursRPAException):
    """Ошибка подключения к прокси."""

    pass


class SearchExecutionError(FedresursRPAException):
    """Ошибка выполнения поиска."""

    pass
