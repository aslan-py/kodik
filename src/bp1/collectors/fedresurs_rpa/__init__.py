"""Fedresurs RPA — Parser for fedresurs.ru with QRATOR bypass."""

from .browser import BrowserManager
from .exceptions import (
    BrowserStartError,
    ElementNotFoundError,
    FedresursRPAException,
    PageLoadError,
    ProxyError,
    SearchExecutionError,
)
from .models import ProxyConfig, SearchRequest, SearchResult
from .parser import FedresursRPA
from .utils import validate_inn

__all__ = [
    "BrowserManager",
    "BrowserStartError",
    "ElementNotFoundError",
    "FedresursRPA",
    "FedresursRPAException",
    "PageLoadError",
    "ProxyConfig",
    "ProxyError",
    "SearchExecutionError",
    "SearchRequest",
    "SearchResult",
    "validate_inn",
]
