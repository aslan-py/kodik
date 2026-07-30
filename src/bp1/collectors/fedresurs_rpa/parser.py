"""Основная RPA-логика для fedresurs.ru с обходом QRATOR."""

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
from .extractor import CompanyDataExtractor
from .logger import get_logger
from .schemas import ProxyConfig, SearchRequest, SearchResult
from .utils import format_proxy_string, generate_filename

logger = get_logger()

_testing_root = str(Path(__file__).resolve().parent.parent)
if _testing_root not in sys.path:
    sys.path.insert(0, _testing_root)


class FedresursRPA:
    """Основной RPA-класс для парсинга fedresurs.ru.

    Поддерживает headless-режим с обходом QRATOR антибот-защиты.

    Использование:
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
        """Выполнить поиск на fedresurs.ru.

        Args:
            request: SearchRequest с именем и опциональными параметрами.

        Returns:
            SearchResult со статусом и путём к файлу.
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
            "Начало поиска для '%s' (ИНН: %s, headless=%s, proxy: %s)",
            request.name,
            request.inn or 'N/A',
            headless,
            proxy_str or 'нет',
        )

        os.makedirs(request.output_dir, exist_ok=True)

        last_error = None
        for attempt in range(1, retry_count + 1):
            try:
                logger.info('Попытка %d/%d', attempt, retry_count)
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
                logger.warning('Попытка %d не удалась: %s', attempt, e)

            if attempt < retry_count:
                delay = get_random_delay() * (2 ** (attempt - 1))
                logger.info('Ожидание %.1f секунд перед повтором...', delay)
                await asyncio.sleep(delay)

        logger.error('Все %d попыток исчерпаны', retry_count)
        return SearchResult(
            success=False,
            name=request.name,
            inn=request.inn,
            error=f'Все {retry_count} попыток исчерпаны: {last_error}',
            error_type='SearchExecutionError',
            timestamp=datetime.now(),
            proxy_used=proxy_str,
        )

    async def _execute_search(
        self,
        request: SearchRequest,
        proxy: ProxyConfig | None,
        headless: bool,
    ) -> SearchResult:
        """Выполнить одну попытку поиска."""
        browser_manager = BrowserManager(
            proxy=proxy,
            user_agent=request.user_agent,
            headless=headless,
        )
        context = await browser_manager.start()
        page = await context.new_page()

        try:
            if request.qrator_bypass:
                logger.info('Переход на %s (обход QRATOR)...', BASE_URL)
                loaded = await bypass_qrator(
                    page, context, BASE_URL, request.timeout
                )
                if not loaded:
                    raise PageLoadError(
                        'Не удалось обойти QRATOR антибот-защиту'
                    )
            else:
                logger.info('Переход на %s...', BASE_URL)
                await page.goto(
                    BASE_URL, wait_until='load', timeout=request.timeout
                )
                await asyncio.sleep(3)

            logger.info('Главная страница загружена успешно')

            await self._select_category(page)
            search_term = request.inn or request.name
            await self._perform_search(page, search_term)
            await self._wait_for_results(page, request.timeout)

            # Клик по первому результату для открытия карточки компании
            await self._open_company_card(page)

            timestamp = datetime.now()
            filename = generate_filename(
                name=request.name,
                inn=request.inn,
                timestamp=timestamp,
            )
            filepath = os.path.join(request.output_dir, filename)

            await self._save_page(page, filepath)

            # Извлечение структурированных данных из карточки компании
            company_data = await self._extract_data_from_page(page)

            logger.info('Поиск успешно завершён: %s', filepath)

            return SearchResult(
                success=True,
                name=request.name,
                inn=request.inn,
                status=company_data.get('status'),
                raw_text=company_data.get('full_text'),
                published_at=company_data.get('published_at'),
                region=company_data.get('region'),
                extra=company_data.get('extra'),
                file_path=filepath,
                timestamp=timestamp,
                proxy_used=format_proxy_string(proxy),
                user_agent_used=browser_manager.user_agent,
            )

        except Exception as e:
            logger.error('Ошибка выполнения поиска: %s', e)
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
        """Выбрать категорию 'Лица' из выпадающего списка."""
        logger.info("Выбор категории 'Лица'")

        try:
            await page.get_by_role('combobox').click()
            await asyncio.sleep(get_human_delay())

            await page.get_by_label('Options list').get_by_text('Лица').click()
            await asyncio.sleep(get_human_delay())
            logger.info("Категория 'Лица' выбрана")
        except Exception as e:
            logger.warning('Выбор категории пропущен: %s', e)

    async def _perform_search(self, page: Page, search_term: str) -> None:
        """Ввести поисковый запрос и нажать кнопку поиска."""
        logger.info('Ввод поискового запроса: %s', search_term)

        try:
            search_input = page.locator(
                SELECTORS['search_input_container']
            ).get_by_role('textbox')
            await search_input.click()
            await search_input.fill(search_term)
            await asyncio.sleep(get_human_delay())

            search_button = page.locator(
                SELECTORS['search_button_container']
            ).get_by_role('button')
            await search_button.click()

            logger.info('Кнопка поиска нажата')
        except Exception as e:
            raise SearchExecutionError(
                f'Не удалось выполнить поиск: {e}'
            ) from e

    async def _wait_for_results(self, page: Page, timeout: int) -> None:
        """Дождаться загрузки результатов поиска в Angular SPA."""
        logger.info('Ожидание результатов поиска...')

        try:
            await page.wait_for_load_state('networkidle', timeout=timeout)
        except Exception:
            logger.info(
                'Таймаут networkidle, ожидание 5с для гидратации Angular...'
            )
            await asyncio.sleep(5)

        # Ожидание появления ссылки на результат
        try:
            await page.wait_for_selector(
                'a:has-text("Вся информация"), .entity-card a, '
                'app-entity-card a',
                timeout=15000,
            )
            logger.info('Результаты поиска отрендерены')
        except Exception:
            logger.info(
                'Ссылка на результат не найдена, продолжаем в любом случае'
            )

    async def _open_company_card(self, page: Page) -> None:
        """Кликнуть по первому результату для открытия карточки компании."""
        logger.info('Открытие карточки компании...')

        try:
            # Ожидание ссылки "Вся информация"
            link = page.locator('a').filter(has_text='Вся информация').first
            await link.wait_for(state='visible', timeout=15000)
            await link.click()

            # Ожидание загрузки страницы карточки компании
            await page.wait_for_load_state('networkidle', timeout=30000)
            await asyncio.sleep(3)

            # Ожидание появления информации о компании
            try:
                await page.wait_for_selector(
                    '.company-name, .entity-header, '
                    'app-company-card, [class*="company"]',
                    timeout=10000,
                )
            except Exception:
                pass

            # Ожидание загрузки данных компании (information-content)
            try:
                await page.wait_for_selector(
                    SELECTORS.get(
                        'company_info_container', '.information-content'
                    ),
                    timeout=15000,
                )
                logger.info('Контейнер информации о компании загружен')
            except Exception:
                logger.info(
                    'Контейнер .information-content не найден, продолжаем'
                )

            # Проверка наличия статуса компании
            try:
                status_selector = SELECTORS.get(
                    'company_status', '.label-item-text'
                )
                status_el = page.locator(status_selector).first
                if await status_el.count() > 0:
                    status_text = await status_el.inner_text()
                    logger.info('Статус компании: %s', status_text.strip())
            except Exception:
                logger.info('Статус компании не обнаружен')

            logger.info('Карточка компании загружена')
        except Exception as e:
            logger.warning('Не удалось открыть карточку компании: %s', e)

    async def _save_page(self, page: Page, filepath: str) -> None:
        """Сохранить отрендеренный DOM как HTML."""
        logger.info('Сохранение страницы в %s', filepath)

        try:
            # Ожидание полной отрисовки Angular
            await asyncio.sleep(3)

            # Получение отрендеренного DOM через JavaScript
            html_content = await page.evaluate(
                'document.documentElement.outerHTML'
            )
            html_content = '<!DOCTYPE html>\n' + html_content

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(
                'Страница сохранена успешно (%d байт)', len(html_content)
            )

        except OSError as e:
            raise PageLoadError(
                f'Не удалось сохранить страницу в {filepath}: {e}'
            ) from e

    async def _extract_data_from_page(self, page: Page) -> dict:
        """Извлечь структурированные данные из карточки компании.

        Args:
            page: Playwright Page с открытой карточкой компании.

        Returns:
            Словарь с извлечёнными данными.
        """
        logger.info('Извлечение данных из карточки компании...')
        extractor = CompanyDataExtractor()
        data = await extractor.extract_company_data(page)

        extra = data.get('extra')
        extra_lines = len(extra.split('\n')) if extra else 0

        logger.info(
            'Извлечено: статус="%s", текст=%d символов, дата=%s, '
            'регион=%s, extra=%d строк',
            data.get('status'),
            len(data.get('full_text') or ''),
            data.get('published_at'),
            data.get('region'),
            extra_lines,
        )
        return data
