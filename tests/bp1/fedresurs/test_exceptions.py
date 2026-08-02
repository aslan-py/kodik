"""Тесты для exceptions.py — иерархия исключений."""

from src.bp1.collectors.fedresurs_rpa.exceptions import (
    BrowserStartError,
    ElementNotFoundError,
    FedresursRPAException,
    PageLoadError,
    ProxyError,
    SearchExecutionError,
)


class TestFedresursRPAException:
    """Базовое исключение."""

    def test_base_exception(self):
        """FedresursRPAException наследуется от Exception."""
        exc = FedresursRPAException('test error')
        assert isinstance(exc, Exception)
        assert str(exc) == 'test error'


class TestBrowserStartError:
    """BrowserStartError."""

    def test_inheritance(self):
        """Наследуется от FedresursRPAException."""
        exc = BrowserStartError('browser error')
        assert isinstance(exc, FedresursRPAException)
        assert isinstance(exc, Exception)

    def test_message(self):
        """Сообщение передаётся корректно."""
        exc = BrowserStartError('Failed to start Chromium')
        assert str(exc) == 'Failed to start Chromium'


class TestPageLoadError:
    """PageLoadError."""

    def test_inheritance(self):
        """Наследуется от FedresursRPAException."""
        exc = PageLoadError('page load error')
        assert isinstance(exc, FedresursRPAException)


class TestElementNotFoundError:
    """ElementNotFoundError."""

    def test_inheritance(self):
        """Наследуется от FedresursRPAException."""
        exc = ElementNotFoundError('element not found')
        assert isinstance(exc, FedresursRPAException)


class TestProxyError:
    """ProxyError."""

    def test_inheritance(self):
        """Наследуется от FedresursRPAException."""
        exc = ProxyError('proxy error')
        assert isinstance(exc, FedresursRPAException)


class TestSearchExecutionError:
    """SearchExecutionError."""

    def test_inheritance(self):
        """Наследуется от FedresursRPAException."""
        exc = SearchExecutionError('search error')
        assert isinstance(exc, FedresursRPAException)
