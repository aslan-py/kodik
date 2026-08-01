"""Модуль извлечения структурированных данных из карточки компании."""

import logging
import re
from typing import Any

from playwright.async_api import Page

from .constants import SELECTORS

logger = logging.getLogger(__name__)


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
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    async def extract_company_data(self, page: Page) -> dict[str, Any]:
        """Извлечь все данные компании со страницы карточки.

        Args:
            page: Playwright Page с открытой карточкой компании.

        Returns:
            Словарь с извлечёнными данными:
                - status: статус компании
                - full_text: полный текст
                - published_at: дата регистрации (из raw_text)
                - region: город регистрации (из raw_text)
                - extra: блок с руководителем (текст из raw_text)
        """
        self._logger.info('Начало извлечения данных компании')

        data: dict[str, Any] = {
            'status': None,
            'full_text': None,
            'published_at': None,
            'region': None,
            'extra': None,
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

        # Извлечение данных из raw_text с помощью маркеров
        if data['full_text']:
            try:
                parsed = self._parse_raw_text(data['full_text'])
                data['published_at'] = parsed.get('published_at')
                data['region'] = parsed.get('region')
                data['extra'] = parsed.get('extra')
                self._logger.info(
                    'Из raw_text: дата=%s, регион=%s, extra=%d строк',
                    data['published_at'],
                    data['region'],
                    len(data['extra'].split('\n')) if data['extra'] else 0,
                )
            except Exception as e:
                self._logger.warning(
                    'Не удалось извлечь данные из raw_text: %s', e
                )
        else:
            self._logger.warning(
                'full_text отсутствует, пропускаем парсинг raw_text'
            )

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

    def _parse_raw_text(self, text: str) -> dict:
        """Извлечь данные из raw_text с помощью маркеров.

        Args:
            text: Полный текст из .information-content.

        Returns:
            Словарь с извлечёнными данными:
                - published_at: дата регистрации
                - region: город регистрации
                - extra: блок с руководителем
        """
        self._logger.debug('Парсинг raw_text (%d символов)', len(text))

        result: dict[str, Any] = {
            'published_at': None,
            'region': None,
            'extra': None,
        }

        # Извлечение даты регистрации
        try:
            published_at = self._extract_between(
                text, 'Дата регистрации', 'Правовая форма (ОКОПФ)'
            )
            if published_at:
                published_at = published_at.strip()
                # Проверка, что это дата в формате DD.MM.YYYY
                date_match = re.search(r'\d{2}\.\d{2}\.\d{4}', published_at)
                if date_match:
                    result['published_at'] = date_match.group()
                    self._logger.debug(
                        'Найдена дата регистрации: %s',
                        result['published_at'],
                    )
                else:
                    self._logger.warning(
                        'Не удалось извлечь дату из: %s', published_at
                    )
            else:
                self._logger.warning(
                    'Маркер "Дата регистрации" не найден в raw_text'
                )
        except Exception as e:
            self._logger.warning(
                'Ошибка при извлечении даты регистрации: %s', e
            )

        # Извлечение региона из адреса
        try:
            address = self._extract_between(
                text, 'Адрес по данным ЕГРЮЛ', 'Дата регистрации'
            )
            if address:
                address = address.strip()
                result['region'] = self._extract_city_from_address(address)
                self._logger.debug(
                    'Найден регион: %s (адрес: %s)',
                    result['region'],
                    address[:50],
                )
            else:
                self._logger.warning(
                    'Маркер "Адрес по данным ЕГРЮЛ" не найден в raw_text'
                )
        except Exception as e:
            self._logger.warning('Ошибка при извлечении региона: %s', e)

        # Извлечение блока с руководителем
        try:
            extra = self._extract_between(
                text,
                'Единоличный исполнительный орган',
                'Дата внесения данных в ЕГРЮЛ',
            )
            if extra:
                # Включаем конечный маркер для полноты блока
                extra_with_end = extra + '\nДата внесения данных в ЕГРЮЛ'
                # Ищем дату после конечного маркера
                date_match = re.search(
                    r'Дата внесения данных в ЕГРЮЛ\n(\d{2}\.\d{2}\.\d{4})',
                    text,
                )
                if date_match:
                    extra_with_end += '\n' + date_match.group(1)
                result['extra'] = extra_with_end.strip()
                self._logger.debug(
                    'Найден блок руководителя: %d строк',
                    len(result['extra'].split('\n')),
                )
            else:
                self._logger.warning(
                    'Маркер "Единоличный исполнительный орган" не найден'
                )
        except Exception as e:
            self._logger.warning(
                'Ошибка при извлечении блока руководителя: %s', e
            )

        return result

    def _extract_between(
        self, text: str, start_marker: str, end_marker: str
    ) -> str | None:
        """Извлечь текст между двумя маркерами.

        Args:
            text: Исходный текст для поиска.
            start_marker: Начальный маркер (строка после него включается).
            end_marker: Конечный маркер (строка до него включается).

        Returns:
            Текст между маркерами или None, если маркеры не найдены.
        """
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                self._logger.debug(
                    'Начальный маркер "%s" не найден', start_marker
                )
                return None

            # Сдвигаем индекс на длину маркера, чтобы начать после него
            content_start = start_idx + len(start_marker)

            end_idx = text.find(end_marker, content_start)
            if end_idx == -1:
                self._logger.debug(
                    'Конечный маркер "%s" не найден после "%s"',
                    end_marker,
                    start_marker,
                )
                return None

            extracted = text[content_start:end_idx].strip()
            self._logger.debug(
                'Извлечено между "%s" и "%s": %d символов',
                start_marker,
                end_marker,
                len(extracted),
            )
            return extracted
        except Exception as e:
            self._logger.warning('Ошибка при извлечении между маркерами: %s', e)
            return None

    def _extract_city_from_address(self, address: str) -> str | None:
        """Извлечь город из адреса с помощью регулярного выражения.

        Поддерживает форматы:
            - г. МОСКВА
            - Г.МОСКВА
            - город Москва

        Args:
            address: Строка адреса.

        Returns:
            Название города с заглавной буквы или None.
        """
        pattern = r'(?:г\.|город|Г\.)\s*([А-Яа-яёЁ\s-]+?)(?:,|$|\.)'
        match = re.search(pattern, address)
        if match:
            city = match.group(1).strip()
            # Нормализация: убираем лишние пробелы, первая буква заглавная
            city = re.sub(r'\s+', ' ', city)
            return city.title()
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
