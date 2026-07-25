"""Browser and context management with anti-detection stealth."""

import sys
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, async_playwright

from .constants import get_random_user_agent
from .exceptions import BrowserStartError, ProxyError
from .logger import get_logger
from .models import ProxyConfig
from src.bp1.collectors.stealth.browser_config import (
    apply_stealth,
    get_context_config,
    get_launch_args
)

logger = get_logger()

_testing_root = str(Path(__file__).resolve().parent.parent)
if _testing_root not in sys.path:
    sys.path.insert(0, _testing_root)


def _build_proxy_dict(proxy: ProxyConfig | None) -> dict | None:
    """Build Playwright proxy dict from ProxyConfig."""
    if proxy is None:
        return None
    proxy_dict = {"server": proxy.server}
    if proxy.username and proxy.password:
        proxy_dict["username"] = proxy.username
        proxy_dict["password"] = proxy.password
    return proxy_dict


class BrowserManager:
    """Async BrowserManager with anti-detection stealth.

    Usage:
        manager = BrowserManager(headless=True)
        page = await manager.start()
        try:
            # work with page
        finally:
            await manager.close()
    """

    def __init__(
        self,
        proxy: ProxyConfig | None = None,
        user_agent: str | None = None,
        headless: bool = True,
    ):
        self._proxy = proxy
        self._user_agent = user_agent or get_random_user_agent()
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> BrowserContext:
        """Launch browser with stealth and return context.

        Returns:
            Playwright BrowserContext (call new_page() to get pages).

        Raises:
            BrowserStartError: If browser fails to start.
            ProxyError: If proxy connection fails.
        """
        try:
            self._playwright = await async_playwright().start()

            launch_kwargs = {
                "headless": self._headless,
                "args": get_launch_args(headless=self._headless),
            }

            proxy_dict = _build_proxy_dict(self._proxy)
            if proxy_dict:
                launch_kwargs["proxy"] = proxy_dict

            logger.info("Launching browser with UA: %s...",
                        self._user_agent[:50])
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)

            context_kwargs = get_context_config(user_agent=self._user_agent)
            self._context = await self._browser.new_context(**context_kwargs)
            await apply_stealth(self._context)

            logger.info(
                "Browser started successfully (headless=%s)", self._headless
            )
            return self._context

        except Exception as e:
            logger.error("Failed to start browser: %s", e)
            await self.close()
            if "proxy" in str(e).lower():
                raise ProxyError(f"Proxy connection failed: {e}") from e
            raise BrowserStartError(f"Failed to start browser: {e}") from e

    async def close(self) -> None:
        """Clean up resources independently."""
        for resource, name in [
            (self._context, "context"),
            (self._browser, "browser"),
            (self._playwright, "playwright"),
        ]:
            if resource is None:
                continue
            try:
                if name == "context":
                    await resource.close()
                elif name == "browser":
                    await resource.close()
                elif name == "playwright":
                    await resource.stop()
            except Exception as e:
                logger.warning("Error closing %s: %s", name, e)

        self._context = None
        self._browser = None
        self._playwright = None
        logger.info("Browser closed")

    @property
    def user_agent(self) -> str:
        """Return current User-Agent."""
        return self._user_agent
