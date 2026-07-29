"""Fedresurs RPA — Парсер для fedresurs.ru с обходом QRATOR."""

from .browser import BrowserManager
from .exceptions import (
    BrowserStartError,
    ElementNotFoundError,
    FedresursRPAException,
    PageLoadError,
    ProxyError,
    SearchExecutionError,
)
from .parser import FedresursRPA
from .schemas import ProxyConfig, SearchRequest, SearchResult
from .utils import validate_inn

__all__ = [
    'BrowserManager',
    'BrowserStartError',
    'ElementNotFoundError',
    'FedresursRPA',
    'FedresursRPAException',
    'PageLoadError',
    'ProxyConfig',
    'ProxyError',
    'SearchExecutionError',
    'SearchRequest',
    'SearchResult',
    'validate_inn',
]
