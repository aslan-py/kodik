from __future__ import annotations

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Playwright,
    sync_playwright,
)

from .config import get_random_user_agent
from .constants import (
    BROWSER_ARGS,
    DEFAULT_TIMEOUT_MS,
    UA_LOG_TRUNCATE,
    VIEWPORT,
)
from .logger import get_logger
from .models import ProxyConfig
from .utils import format_proxy_string

logger = get_logger(__name__)


class BrowserManager:
    """Управление браузером Playwright: запуск, контекст, очистка."""

    def __init__(
        self,
        headless: bool = True,
        proxy: ProxyConfig | None = None,
        user_agent: str | None = None,
        timeout: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._headless = headless
        self._proxy = proxy
        self._user_agent = user_agent or get_random_user_agent()
        self._timeout = timeout
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

    def start(self) -> BrowserManager:
        """Запускает браузер и создаёт контекст."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self._headless,
            args=BROWSER_ARGS,
        )

        context_kwargs: dict = {
            'user_agent': self._user_agent,
            'viewport': VIEWPORT,
        }

        if self._proxy:
            proxy_dict: dict = {'server': self._proxy.server}
            if self._proxy.username:
                proxy_dict['username'] = self._proxy.username
            if self._proxy.password:
                proxy_dict['password'] = self._proxy.password
            context_kwargs['proxy'] = proxy_dict

        self._context = self._browser.new_context(**context_kwargs)
        self._context.set_default_timeout(self._timeout)

        proxy_log = (
            format_proxy_string(self._proxy.server, self._proxy.username)
            if self._proxy
            else None
        )
        logger.info(
            'Браузер запущен. UA=%s, proxy=%s, headless=%s',
            self._user_agent[:UA_LOG_TRUNCATE],
            proxy_log,
            self._headless,
        )
        return self

    def stop(self) -> None:
        """Закрывает контекст и браузер."""
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.info('Браузер закрыт.')

    def __enter__(self) -> BrowserManager:
        return self.start()

    def __exit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: object
    ) -> None:
        self.stop()
