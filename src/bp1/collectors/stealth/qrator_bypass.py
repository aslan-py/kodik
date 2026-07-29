"""Обход QRATOR антибот-защиты через двухшаговую навигацию."""

from playwright.async_api import BrowserContext, Page

# Стандартные тайминги QRATOR (мс)
QRATOR_CHALLENGE_WAIT_MS = 25000
QRATOR_POST_NAVIGATION_WAIT_MS = 3000
QRATOR_LOGO_CLICK_WAIT_MS = 5000


async def bypass_qrator(
    page: Page,
    context: BrowserContext,
    target_url: str = 'https://fedresurs.ru',
    timeout: int = 60000,
) -> bool:
    """Перейти на fedresurs.ru в обход QRATOR антибот-защиты.

    Процесс QRATOR:
    1. Первый запрос -> 401 с JS-челленджем
    2. Ожидание ~25с для установки куки qrator_jsr
    3. Переход на /search (возвращает 200)
    4. Клик по логотипу для перехода на главную страницу

    Args:
        page: Playwright Page.
        context: BrowserContext (нужен для cookies).
        target_url: Базовый URL.
        timeout: Таймаут навигации в мс.

    Returns:
        True, если главная страница загружена успешно.
    """
    response = await page.goto(target_url, wait_until='load', timeout=timeout)
    status = response.status if response else 0

    if status not in (401, 403):
        return status == 200

    await page.wait_for_timeout(QRATOR_CHALLENGE_WAIT_MS)

    cookies = await context.cookies()
    cookie_names = [c['name'] for c in cookies]

    if 'qrator_jsr' not in cookie_names:
        return False

    search_response = await page.goto(
        f'{target_url}/search', wait_until='load', timeout=30000
    )
    await page.wait_for_timeout(QRATOR_POST_NAVIGATION_WAIT_MS)

    if not search_response or search_response.status != 200:
        return False

    logo = await page.query_selector('a[href="/"]')
    if logo:
        await logo.click()
        await page.wait_for_timeout(QRATOR_LOGO_CLICK_WAIT_MS)

    return True
