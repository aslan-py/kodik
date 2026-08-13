"""Headless browser-проверка навигации и visual evidence админки.

Запуск намеренно явный: ``KODIK_RUN_ADMIN_BROWSER_TESTS=1 pytest
tests/admin/test_browser_navigation.py``. Для фиксации screenshots дополнительно
задаётся ``KODIK_ADMIN_SCREENSHOT_DIR``.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.async_api import Browser, Page, async_playwright, expect
from sqlalchemy import delete

from api.security import hash_password
from core.database import AsyncSessionLocal
from core.enums import UserRole
from src.bp5.models import User

pytestmark = pytest.mark.skipif(
    os.getenv('KODIK_RUN_ADMIN_BROWSER_TESTS') != '1',
    reason='set KODIK_RUN_ADMIN_BROWSER_TESTS=1 for headless UI checks',
)

_EXPECTED_SECTIONS = [
    ('pipeline', 'Пайплайн', None),
    ('parsing', 'Настройки парсинга', 'Competitor'),
    ('references', 'Настройки справочников', 'Region'),
    ('alerting', 'Настройки алертинга', 'EventType'),
    ('final', 'Финальные таблицы', 'RawItem'),
]
_REMOVED_SECTION_TITLES = {
    'Пользователи',
    'Витрина',
    'План действий',
    'Настройки валидации',
    'Данные конвейера',
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope='module')
def live_admin_url() -> Iterator[str]:
    port = _free_port()
    url = f'http://127.0.0.1:{port}/admin/'
    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    process = subprocess.Popen(
        [
            sys.executable,
            '-m',
            'uvicorn',
            'api.main:app',
            '--host',
            '127.0.0.1',
            '--port',
            str(port),
            '--no-access-log',
            '--log-level',
            'warning',
        ],
        cwd=Path(__file__).parents[2],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail('uvicorn stopped before the browser test')
            try:
                with urllib.request.urlopen(url, timeout=0.25) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail('uvicorn did not become ready')
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope='module')
async def qa_credentials() -> AsyncIterator[tuple[str, str]]:
    email = f'admin-browser-{uuid4().hex}@local.test'
    password = 'KodikBrowser123!'
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            full_name='Admin Browser Test',
            password_hash=hash_password(password),
            role=UserRole.admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()
    try:
        yield email, password
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()


async def _login(page: Page, url: str, credentials: tuple[str, str]) -> None:
    await page.goto(url, wait_until='networkidle')
    await page.locator('input').nth(0).fill(credentials[0])
    await page.locator('input').nth(1).fill(credentials[1])
    await page.locator('button').click()
    await page.wait_for_url(lambda value: '#/sign-in' not in value)
    await expect(page.locator('.kodik-section-banner')).to_be_visible()


async def _visible_section_titles(page: Page) -> list[str]:
    return await page.locator(
        'ul.ant-menu-root > li[data-kodik-section]:visible'
    ).evaluate_all(
        """items => items.map(item => {
          const title = item.matches('[role="menuitem"]')
            ? item
            : item.querySelector(':scope > [role="menuitem"]');
          return title.textContent.trim();
        })"""
    )


async def _open_model(page: Page, section_id: str, model: str) -> None:
    section = page.locator(
        f'[data-kodik-section="{section_id}"] > [role="menuitem"]'
    )
    if await section.get_attribute('aria-expanded') == 'false':
        await section.click()
    await page.locator(f'[data-menu-id$="-{model}"]').click()


async def _expand_desktop_sections(page: Page) -> None:
    for section_id, _title, model in _EXPECTED_SECTIONS:
        if model is None:
            continue
        section = page.locator(
            f'[data-kodik-section="{section_id}"] > [role="menuitem"]'
        )
        if await section.get_attribute('aria-expanded') == 'false':
            await section.click()


async def _capture_matrix(
    browser: Browser,
    base_url: str,
    credentials: tuple[str, str],
    screenshot_dir: Path,
) -> None:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    for theme in ('light', 'dark'):
        for layout, viewport in (
            ('desktop', {'width': 1440, 'height': 1100}),
            ('minimum', {'width': 768, 'height': 900}),
        ):
            for menu_state in ('compact', 'expanded'):
                context = await browser.new_context(
                    viewport=viewport,
                    color_scheme=theme,
                )
                page = await context.new_page()
                await _login(page, base_url, credentials)
                if layout == 'desktop' and menu_state == 'expanded':
                    await _expand_desktop_sections(page)
                if layout == 'minimum' and menu_state == 'expanded':
                    settings_menu = page.locator('[data-icon="setting"]')
                    await expect(settings_menu).to_be_visible()
                    await settings_menu.click()
                    await page.wait_for_timeout(200)
                assert (
                    await page.locator('body').get_attribute('data-theme')
                    == theme
                )
                assert await page.evaluate(
                    'document.documentElement.scrollWidth <= '
                    'document.documentElement.clientWidth'
                )
                await page.evaluate(
                    """() => {
                      window.scrollTo(0, 0);
                      document.querySelectorAll('.ant-menu-root').forEach(
                        menu => { menu.scrollTop = 0; }
                      );
                    }"""
                )
                await page.screenshot(
                    path=screenshot_dir / f'{layout}-{menu_state}-{theme}.png',
                    full_page=False,
                )
                await context.close()


async def test_navigation_banners_direct_urls_and_visual_matrix(
    live_admin_url: str,
    qa_credentials: tuple[str, str],
    tmp_path: Path,
) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={'width': 1440, 'height': 1100},
            color_scheme='light',
        )
        await _login(page, live_admin_url, qa_credentials)

        assert await _visible_section_titles(page) == [
            title for _section, title, _model in _EXPECTED_SECTIONS
        ]
        assert not _REMOVED_SECTION_TITLES.intersection(
            await _visible_section_titles(page)
        )
        hidden_pipeline = page.locator(
            '[data-kodik-section="pipeline"][data-kodik-hidden="true"]'
        )
        await expect(hidden_pipeline).to_have_count(1)
        await expect(page.locator('[data-menu-id$="-dashboard"]')).to_have_text(
            'Пайплайн'
        )

        for section_id, title, model in _EXPECTED_SECTIONS:
            if model is None:
                await page.locator('[data-menu-id$="-dashboard"]').click()
            else:
                await _open_model(page, section_id, model)
            await expect(
                page.locator('.kodik-section-banner__title')
            ).to_have_text(title)

        for _section_id, title, model in _EXPECTED_SECTIONS[1:]:
            await page.goto(
                f'{live_admin_url}#/list/{model}', wait_until='networkidle'
            )
            await expect(
                page.locator('.kodik-section-banner__title')
            ).to_have_text(title)

        configured_dir = os.getenv('KODIK_ADMIN_SCREENSHOT_DIR')
        screenshot_dir = Path(configured_dir) if configured_dir else tmp_path
        await _capture_matrix(
            browser,
            live_admin_url,
            qa_credentials,
            screenshot_dir,
        )
        await browser.close()
