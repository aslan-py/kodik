"""Browser manager: запуск, контекст, очистка (async + stealth)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
    Playwright,
    async_playwright,
)

from src.bp1.collectors.stealth.browser_config import (
    apply_stealth,
    get_context_config,
    get_launch_args,
)

from .config import get_random_user_agent
from .constants import DEFAULT_TIMEOUT_MS, UA_LOG_TRUNCATE
from .schemas import ProxyConfig
from .utils import format_proxy_string

logger = logging.getLogger(__name__)

_testing_root = str(Path(__file__).resolve().parent.parent)
if _testing_root not in sys.path:
    sys.path.insert(0, _testing_root)


def _build_proxy_dict(proxy: ProxyConfig | None) -> dict | None:
    """Собрать словарь прокси для Playwright из ProxyConfig."""
    if proxy is None:
        return None
    proxy_dict = {'server': proxy.server}
    if proxy.username and proxy.password:
        proxy_dict['username'] = proxy.username
        proxy_dict['password'] = proxy.password
    return proxy_dict


class BrowserManager:
    """Асинхронный менеджер браузера с антидетект-стелсом.

    Использование:
        manager = BrowserManager(headless=True)
        await manager.start()
        try:
            page = await manager.context.new_page()
            # работа со страницей
        finally:
            await manager.stop()
    """

    def __init__(
        self,
        headless: bool = True,
        proxy: ProxyConfig | None = None,
        user_agent: str | None = None,
        timeout: int = DEFAULT_TIMEOUT_MS,
        use_stealth: bool = True,
    ) -> None:
        self._headless = headless
        self._proxy = proxy
        self._user_agent = user_agent or get_random_user_agent()
        self._timeout = timeout
        self._use_stealth = use_stealth
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @property
    def user_agent(self) -> str:
        return self._user_agent

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError(
                'BrowserManager не инициализирован. Вызовите start().'
            )
        return self._context

    async def start(self) -> BrowserManager:
        """Запускает браузер со стелсом и создаёт контекст."""
        self._playwright = await async_playwright().start()

        # Аргументы запуска: если стелс отключён — используем 'old' headless
        # для лучшей маскировки на kad.arbitr.ru
        headless_mode = 'new' if self._use_stealth else 'old'
        launch_args = get_launch_args(
            headless=self._headless,
            headless_mode=headless_mode,
        )

        launch_kwargs = {
            'headless': self._headless,
            'args': launch_args,
        }

        proxy_dict = _build_proxy_dict(self._proxy)
        if proxy_dict:
            launch_kwargs['proxy'] = proxy_dict

        logger.info(
            'Запуск браузера с UA: %s...',
            self._user_agent[:UA_LOG_TRUNCATE],
        )
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

        context_kwargs = get_context_config(user_agent=self._user_agent)
        self._context = await self._browser.new_context(**context_kwargs)
        if self._use_stealth:
            await apply_stealth(self._context)
        else:
            # Для kad.arbitr.ru — отключаем проблемные JS-инъекции,
            # которые ломают обработчики событий на сайте
            logger.info(
                'Применён выборочный стелс (skip_webdriver, skip_chrome, '
                'skip_plugins, skip_navigator, skip_webgl)'
            )
            await apply_stealth(
                self._context,
                skip_webdriver=True,
                skip_chrome=True,
                skip_plugins=True,
                skip_navigator=True,
                skip_webgl=True,
            )
        self._context.set_default_timeout(self._timeout)

        proxy_log = (
            format_proxy_string(self._proxy.server, self._proxy.username)
            if self._proxy
            else None
        )
        logger.info(
            'Браузер успешно запущен (headless=%s, proxy=%s)',
            self._headless,
            proxy_log,
        )
        return self

    async def stop(self) -> None:
        """Закрывает контекст и браузер."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info('Браузер закрыт.')
