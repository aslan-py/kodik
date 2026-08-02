"""Тесты для browser.py — BrowserManager, _build_proxy_dict."""

import pytest

from src.bp1.collectors.fedresurs_rpa.browser import (
    BrowserManager,
    _build_proxy_dict,
)
from src.bp1.collectors.fedresurs_rpa.schemas import ProxyConfig

# ===========================================================================
# _build_proxy_dict
# ===========================================================================


class TestBuildProxyDict:
    """Тесты для _build_proxy_dict()."""

    def test_with_auth(self):
        """Прокси с username и password."""
        proxy = ProxyConfig(
            server='http://1.2.3.4:8080', username='user', password='pass'
        )
        result = _build_proxy_dict(proxy)
        assert result == {
            'server': 'http://1.2.3.4:8080',
            'username': 'user',
            'password': 'pass',
        }

    def test_without_auth(self):
        """Прокси без авторизации."""
        proxy = ProxyConfig(server='http://1.2.3.4:8080')
        result = _build_proxy_dict(proxy)
        assert result == {'server': 'http://1.2.3.4:8080'}

    def test_none(self):
        """None — возвращает None."""
        assert _build_proxy_dict(None) is None

    def test_empty_credentials(self):
        """Пустые username/password не включаются."""
        proxy = ProxyConfig(
            server='http://1.2.3.4:8080', username='', password=''
        )
        result = _build_proxy_dict(proxy)
        assert result == {'server': 'http://1.2.3.4:8080'}
        assert 'username' not in result


# ===========================================================================
# BrowserManager
# ===========================================================================


class TestBrowserManagerInit:
    """Тесты для BrowserManager.__init__()."""

    def test_default_user_agent(self):
        """User-Agent устанавливается по умолчанию."""
        manager = BrowserManager()
        assert manager.user_agent is not None
        assert manager.user_agent.startswith('Mozilla/5.0')

    def test_custom_user_agent(self):
        """Кастомный User-Agent."""
        manager = BrowserManager(user_agent='Custom UA')
        assert manager.user_agent == 'Custom UA'

    def test_default_headless(self):
        """headless=True по умолчанию."""
        manager = BrowserManager()
        assert manager._headless is True

    def test_custom_headless(self):
        """headless=False."""
        manager = BrowserManager(headless=False)
        assert manager._headless is False

    def test_initial_state(self):
        """Начальное состояние — все ресурсы None."""
        manager = BrowserManager()
        assert manager._playwright is None
        assert manager._browser is None
        assert manager._context is None

    def test_with_proxy(self):
        """Прокси передаётся в конструктор."""
        proxy = ProxyConfig(server='http://1.2.3.4:8080')
        manager = BrowserManager(proxy=proxy)
        assert manager._proxy == proxy


@pytest.mark.asyncio
class TestBrowserManagerStart:
    """Тесты для BrowserManager.start() — с моками."""

    async def test_start_success(self, mocker):
        """Успешный запуск браузера."""
        # Мокаем playwright
        mock_playwright = mocker.AsyncMock()
        mock_chromium = mocker.AsyncMock()
        mock_browser = mocker.AsyncMock()
        mock_context = mocker.AsyncMock()

        mock_playwright.chromium = mock_chromium
        mock_chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context

        # Мокаем async_playwright
        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.browser.async_playwright',
            return_value=mocker.AsyncMock(
                start=mocker.AsyncMock(return_value=mock_playwright)
            ),
        )
        # Мокаем apply_stealth и get_context_config
        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.browser.apply_stealth',
            return_value=None,
        )
        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.browser.get_context_config',
            return_value={},
        )
        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.browser.get_launch_args',
            return_value=[],
        )

        manager = BrowserManager(headless=True)
        result = await manager.start()

        assert result == mock_context
        mock_chromium.launch.assert_awaited_once()
        mock_browser.new_context.assert_awaited_once()

    async def test_start_browser_error(self, mocker):
        """Ошибка запуска браузера — BrowserStartError."""
        from src.bp1.collectors.fedresurs_rpa.exceptions import (
            BrowserStartError,
        )

        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.browser.async_playwright',
            side_effect=Exception('Failed to launch'),
        )

        manager = BrowserManager()
        with pytest.raises(BrowserStartError):
            await manager.start()

    async def test_start_proxy_error(self, mocker):
        """Ошибка прокси — ProxyError."""
        from src.bp1.collectors.fedresurs_rpa.exceptions import ProxyError

        mock_playwright = mocker.AsyncMock()
        mock_chromium = mocker.AsyncMock()
        mock_chromium.launch.side_effect = Exception('proxy connection failed')

        mock_playwright.chromium = mock_chromium
        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.browser.async_playwright',
            return_value=mocker.AsyncMock(
                start=mocker.AsyncMock(return_value=mock_playwright)
            ),
        )

        manager = BrowserManager(
            proxy=ProxyConfig(server='http://1.2.3.4:8080')
        )
        with pytest.raises(ProxyError):
            await manager.start()


@pytest.mark.asyncio
class TestBrowserManagerClose:
    """Тесты для BrowserManager.close()."""

    async def test_close_all_resources(self, mocker):
        """Закрытие всех ресурсов."""
        manager = BrowserManager()
        mock_context = mocker.AsyncMock()
        mock_browser = mocker.AsyncMock()
        mock_playwright = mocker.AsyncMock()
        manager._context = mock_context
        manager._browser = mock_browser
        manager._playwright = mock_playwright

        await manager.close()

        mock_context.close.assert_awaited_once()
        mock_browser.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()

        assert manager._context is None
        assert manager._browser is None
        assert manager._playwright is None

    async def test_close_partial_resources(self, mocker):
        """Закрытие при частично инициализированных ресурсах."""
        manager = BrowserManager()
        mock_context = mocker.AsyncMock()
        manager._context = mock_context
        # _browser и _playwright — None

        await manager.close()

        mock_context.close.assert_awaited_once()
        assert manager._context is None

    async def test_close_with_error(self, mocker):
        """Ошибка при закрытии не прерывает очистку."""
        manager = BrowserManager()
        mock_context = mocker.AsyncMock()
        mock_context.close.side_effect = Exception('close error')
        mock_browser = mocker.AsyncMock()
        mock_playwright = mocker.AsyncMock()
        manager._context = mock_context
        manager._browser = mock_browser
        manager._playwright = mock_playwright

        # Не должно быть исключения
        await manager.close()

        mock_browser.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()
