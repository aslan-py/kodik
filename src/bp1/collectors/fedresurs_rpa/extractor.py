"""Модуль извлечения структурированных данных из карточки компании."""

import logging
from typing import Any

from playwright.async_api import Page

from .constants import SELECTORS
from .logger import get_logger

logger = get_logger(__name__)


class ExtractionError(Exception):
    """Ошибка при извлечении данных из карточки компании."""

    pass


class CompanyDataExtractor:
    """Класс для извлечения структурированных данных из карточки компании.

    Использование:
        extractor = CompanyDataExtractor()
        data = await extractor.extract_company_data(page)
        print(data['status'], data['full_text'][:100])
    """

    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or get_logger(self.__class__.__name__)

    async def extract_company_data(self, page: Page) -> dict[str, Any]:
        """Извлечь все данные компании со страницы карточки.

        Args:
            page: Playwright Page с открытой карточкой компании.

        Returns:
            Словарь с извлечёнными данными:
                - status: статус компании (Действующее/Ликвидировано и т.д.)
                - full_text: полный текст из information-content
                - raw_html: исходный HTML information-content (опционально)
        """
        self._logger.info('Начало извлечения данных компании')

        data: dict[str, Any] = {
            'status': None,
            'full_text': None,
        }

        # Извлечение статуса компании
        try:
            data['status'] = await self._extract_status(page)
            self._logger.info('Статус компании: %s', data['status'])
        except Exception as e:
            self._logger.warning('Не удалось извлечь статус: %s', e)

        # Извлечение полного текста
        try:
            data['full_text'] = await self._extract_full_text(page)
            self._logger.info(
                'Текст извлечён: %d символов',
                len(data['full_text']) if data['full_text'] else 0,
            )
        except Exception as e:
            self._logger.warning('Не удалось извлечь полный текст: %s', e)

        self._logger.info('Извлечение данных завершено')
        return data

    async def _extract_status(self, page: Page) -> str | None:
        """Извлечь статус компании из элемента .label-item-text.

        Args:
            page: Playwright Page.

        Returns:
            Строка статуса или None, если элемент не найден.
        """
        selector = SELECTORS.get('company_status', '.label-item-text')
        self._logger.debug('Поиск статуса по селектору: %s', selector)

        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                status_text = await element.inner_text()
                return status_text.strip()
            else:
                self._logger.debug('Элемент статуса не найден')
                return None
        except Exception as e:
            self._logger.debug('Ошибка при извлечении статуса: %s', e)
            return None

    async def _extract_full_text(self, page: Page) -> str | None:
        """Извлечь весь текст из контейнера .information-content.

        Args:
            page: Playwright Page.

        Returns:
            Текст контейнера или None, если элемент не найден.
        """
        selector = SELECTORS.get(
            'company_info_container', '.information-content'
        )
        self._logger.debug('Поиск контейнера по селектору: %s', selector)

        try:
            # Пробуем через innerText для чистого текста
            full_text = await page.evaluate(
                f"""() => {{
                    const el = document.querySelector('{selector}');
                    return el ? el.innerText : null;
                }}"""
            )
            if full_text:
                return full_text.strip()

            # Fallback: пробуем через locator
            self._logger.debug('Fallback: поиск через locator для %s', selector)
            element = page.locator(selector).first
            if await element.count() > 0:
                return (await element.inner_text()).strip()

            return None
        except Exception as e:
            self._logger.debug('Ошибка при извлечении текста: %s', e)
            return None

    async def _extract_with_fallback(
        self,
        page: Page,
        primary_selector: str,
        fallback_selector: str | None = None,
    ) -> str | None:
        """Извлечь данные с fallback-механизмом.

        Сначала пробует primary_selector, затем fallback_selector.

        Args:
            page: Playwright Page.
            primary_selector: Основной CSS-селектор.
            fallback_selector: Запасной CSS-селектор.

        Returns:
            Текст элемента или None.
        """
        # Попытка через evaluate (быстрее)
        for selector in [primary_selector, fallback_selector]:
            if not selector:
                continue
            try:
                text = await page.evaluate(
                    f"""() => {{
                        const el = document.querySelector('{selector}');
                        return el ? el.innerText.trim() : null;
                    }}"""
                )
                if text:
                    return text
            except Exception:
                continue

        # Финальный fallback через locator
        for selector in [primary_selector, fallback_selector]:
            if not selector:
                continue
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    return (await element.inner_text()).strip()
            except Exception:
                continue

        return None
