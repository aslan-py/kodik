"""QRATOR anti-bot bypass via two-step navigation."""

from playwright.async_api import BrowserContext, Page

# Default QRATOR timing (ms)
QRATOR_CHALLENGE_WAIT_MS = 25000
QRATOR_POST_NAVIGATION_WAIT_MS = 3000
QRATOR_LOGO_CLICK_WAIT_MS = 5000


async def bypass_qrator(
    page: Page,
    context: BrowserContext,
    target_url: str = "https://fedresurs.ru",
    timeout: int = 60000,
) -> bool:
    """Navigate to fedresurs.ru bypassing QRATOR anti-bot.

    QRATOR flow:
    1. Initial request -> 401 with JS challenge
    2. Wait ~25s for qrator_jsr cookie to be set
    3. Navigate to /search (returns 200)
    4. Click logo to reach main page

    Args:
        page: Playwright Page.
        context: BrowserContext (needed for cookies).
        target_url: Base URL.
        timeout: Navigation timeout in ms.

    Returns:
        True if main page loaded successfully.
    """
    response = await page.goto(target_url, wait_until="load", timeout=timeout)
    status = response.status if response else 0

    if status not in (401, 403):
        return status == 200

    await page.wait_for_timeout(QRATOR_CHALLENGE_WAIT_MS)

    cookies = await context.cookies()
    cookie_names = [c["name"] for c in cookies]

    if "qrator_jsr" not in cookie_names:
        return False

    search_response = await page.goto(
        f"{target_url}/search", wait_until="load", timeout=30000
    )
    await page.wait_for_timeout(QRATOR_POST_NAVIGATION_WAIT_MS)

    if not search_response or search_response.status != 200:
        return False

    logo = await page.query_selector('a[href="/"]')
    if logo:
        await logo.click()
        await page.wait_for_timeout(QRATOR_LOGO_CLICK_WAIT_MS)

    return True
