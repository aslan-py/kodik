"""Main RPA logic for fedresurs.ru with QRATOR bypass."""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page
from stealth.qrator_bypass import bypass_qrator

from .browser import BrowserManager
from .constants import (
    BASE_URL,
    DEFAULT_RETRY_COUNT,
    SELECTORS,
    get_human_delay,
    get_random_delay,
)
from .exceptions import (
    PageLoadError,
    SearchExecutionError,
)
from .logger import get_logger
from .models import ProxyConfig, SearchRequest, SearchResult
from .utils import format_proxy_string, generate_filename

logger = get_logger()

_testing_root = str(Path(__file__).resolve().parent.parent)
if _testing_root not in sys.path:
    sys.path.insert(0, _testing_root)


class FedresursRPA:
    """Main RPA class for parsing fedresurs.ru.

    Supports headless mode via QRATOR anti-bot bypass.

    Usage:
        parser = FedresursRPA()
        request = SearchRequest(name='ООО "Компания"', inn="1234567890")
        result = await parser.search(request)
    """

    def __init__(
        self,
        default_proxy: ProxyConfig | None = None,
        default_headless: bool = True,
    ):
        self._default_proxy = default_proxy
        self._default_headless = default_headless

    async def search(self, request: SearchRequest) -> SearchResult:
        """Execute search on fedresurs.ru.

        Args:
            request: SearchRequest with name and optional parameters.

        Returns:
            SearchResult with status and file path.
        """
        proxy = request.proxy or self._default_proxy
        headless = (
            request.headless
            if request.headless is not None
            else self._default_headless
        )
        retry_count = (
            request.retry_count
            if request.retry_count is not None
            else DEFAULT_RETRY_COUNT
        )

        proxy_str = format_proxy_string(proxy)
        logger.info(
            "Starting search for '%s' (INN: %s, headless=%s, proxy: %s)",
            request.name,
            request.inn or "N/A",
            headless,
            proxy_str or "none",
        )

        os.makedirs(request.output_dir, exist_ok=True)

        last_error = None
        for attempt in range(1, retry_count + 1):
            try:
                logger.info("Attempt %d/%d", attempt, retry_count)
                result = await self._execute_search(
                    request=request,
                    proxy=proxy,
                    headless=headless,
                )
                if result.success:
                    return result
                last_error = result.error
            except Exception as e:
                last_error = str(e)
                logger.warning("Attempt %d failed: %s", attempt, e)

            if attempt < retry_count:
                delay = get_random_delay() * (2 ** (attempt - 1))
                logger.info("Waiting %.1f seconds before retry...", delay)
                await asyncio.sleep(delay)

        logger.error("All %d attempts failed", retry_count)
        return SearchResult(
            success=False,
            name=request.name,
            inn=request.inn,
            error=f"All {retry_count} attempts failed: {last_error}",
            error_type="SearchExecutionError",
            timestamp=datetime.now(),
            proxy_used=proxy_str,
        )

    async def _execute_search(
        self,
        request: SearchRequest,
        proxy: ProxyConfig | None,
        headless: bool,
    ) -> SearchResult:
        """Execute single search attempt."""
        browser_manager = BrowserManager(
            proxy=proxy,
            user_agent=request.user_agent,
            headless=headless,
        )
        context = await browser_manager.start()
        page = await context.new_page()

        try:
            if request.qrator_bypass:
                logger.info("Navigating to %s (QRATOR bypass)...", BASE_URL)
                loaded = await bypass_qrator(
                    page, context, BASE_URL, request.timeout
                )
                if not loaded:
                    raise PageLoadError(
                        "Failed to bypass QRATOR anti-bot protection")
            else:
                logger.info("Navigating to %s...", BASE_URL)
                await page.goto(
                    BASE_URL,
                    wait_until="load",
                    timeout=request.timeout
                )
                await asyncio.sleep(3)

            logger.info("Main page loaded successfully")

            await self._select_category(page)
            search_term = request.inn or request.name
            await self._perform_search(page, search_term)
            await self._wait_for_results(page, request.timeout)

            # Click on first result to open company card
            await self._open_company_card(page)

            timestamp = datetime.now()
            filename = generate_filename(
                name=request.name,
                inn=request.inn,
                timestamp=timestamp,
            )
            filepath = os.path.join(request.output_dir, filename)

            await self._save_page(page, filepath)

            logger.info("Search completed successfully: %s", filepath)

            return SearchResult(
                success=True,
                name=request.name,
                inn=request.inn,
                file_path=filepath,
                timestamp=timestamp,
                proxy_used=format_proxy_string(proxy),
                user_agent_used=browser_manager.user_agent,
            )

        except Exception as e:
            logger.error("Search execution failed: %s", e)
            return SearchResult(
                success=False,
                name=request.name,
                inn=request.inn,
                error=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now(),
                proxy_used=format_proxy_string(proxy),
                user_agent_used=browser_manager.user_agent,
            )
        finally:
            await browser_manager.close()

    async def _select_category(self, page: Page) -> None:
        """Select 'Лица' category from dropdown."""
        logger.info("Selecting 'Лица' category")

        try:
            await page.get_by_role("combobox").click()
            await asyncio.sleep(get_human_delay())

            await page.get_by_label("Options list").get_by_text("Лица").click()
            await asyncio.sleep(get_human_delay())
            logger.info("'Лица' category selected")
        except Exception as e:
            logger.warning("Category selection skipped: %s", e)

    async def _perform_search(self, page: Page, search_term: str) -> None:
        """Enter search term and click search button."""
        logger.info("Entering search term: %s", search_term)

        try:
            search_input = page.locator(
                SELECTORS["search_input_container"]
            ).get_by_role("textbox")
            await search_input.click()
            await search_input.fill(search_term)
            await asyncio.sleep(get_human_delay())

            search_button = page.locator(
                SELECTORS["search_button_container"]
            ).get_by_role("button")
            await search_button.click()

            logger.info("Search button clicked")
        except Exception as e:
            raise SearchExecutionError(f"Failed to perform search: {e}") from e

    async def _wait_for_results(self, page: Page, timeout: int) -> None:
        """Wait for Angular SPA to load search results."""
        logger.info("Waiting for search results...")

        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            logger.info(
                "networkidle timeout, waiting 5s for Angular hydration...")
            await asyncio.sleep(5)

        # Wait for result link to appear
        try:
            await page.wait_for_selector(
                'a:has-text("Вся информация"), .entity-card a, '
                'app-entity-card a',
                timeout=15000,
            )
            logger.info("Search results rendered")
        except Exception:
            logger.info("Result link not found, will try to proceed anyway")

    async def _open_company_card(self, page: Page) -> None:
        """Click on first search result to open company card page."""
        logger.info("Opening company card...")

        try:
            # Wait for the "Вся информация" link
            link = page.locator('a').filter(has_text="Вся информация").first
            await link.wait_for(state="visible", timeout=15000)
            await link.click()

            # Wait for company card page to load
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Wait for company info to appear
            try:
                await page.wait_for_selector(
                    '.company-name, .entity-header, '
                    'app-company-card, [class*="company"]',
                    timeout=10000,
                )
            except Exception:
                pass

            logger.info("Company card loaded")
        except Exception as e:
            logger.warning("Could not open company card: %s", e)

    async def _save_page(self, page: Page, filepath: str) -> None:
        """Save rendered DOM as HTML."""
        logger.info("Saving page to %s", filepath)

        try:
            # Wait for Angular to fully render
            await asyncio.sleep(3)

            # Get rendered DOM via JavaScript
            html_content = await page.evaluate(
                "document.documentElement.outerHTML"
            )
            html_content = "<!DOCTYPE html>\n" + html_content

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.info("Page saved successfully (%d bytes)",
                        len(html_content))

        except OSError as e:
            raise PageLoadError(
                f"Failed to save page to {filepath}: {e}") from e
