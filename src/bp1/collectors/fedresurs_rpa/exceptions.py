"""Custom exceptions for fedresurs_rpa package."""


class FedresursRPAException(Exception):
    """Base exception for fedresurs_rpa package."""

    pass


class BrowserStartError(FedresursRPAException):
    """Error starting browser."""

    pass


class PageLoadError(FedresursRPAException):
    """Error loading page."""

    pass


class ElementNotFoundError(FedresursRPAException):
    """Element not found on page."""

    pass


class ProxyError(FedresursRPAException):
    """Proxy connection error."""

    pass


class SearchExecutionError(FedresursRPAException):
    """Error during search execution."""

    pass
