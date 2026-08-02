"""Тесты для extractor.py — CompanyDataExtractor."""

import pytest

from src.bp1.collectors.fedresurs_rpa.extractor import CompanyDataExtractor

# ===========================================================================
# _extract_between
# ===========================================================================


class TestExtractBetween:
    """Тесты для _extract_between()."""

    def setup_method(self):
        self.extractor = CompanyDataExtractor()

    def test_basic_extraction(self):
        """Извлечение текста между двумя маркерами."""
        text = 'Начало Данные Конец'
        result = self.extractor._extract_between(text, 'Начало', 'Конец')
        assert result == 'Данные'

    def test_with_whitespace(self):
        """Пробелы вокруг данных обрезаются."""
        text = 'Start   Content   End'
        result = self.extractor._extract_between(text, 'Start', 'End')
        assert result == 'Content'

    def test_start_marker_not_found(self):
        """Стартовый маркер не найден."""
        result = self.extractor._extract_between('abc', 'xyz', 'end')
        assert result is None

    def test_end_marker_not_found(self):
        """Конечный маркер не найден."""
        result = self.extractor._extract_between('start abc', 'start', 'end')
        assert result is None

    def test_empty_between(self):
        """Пустое содержимое между маркерами."""
        result = self.extractor._extract_between('a b', 'a', 'b')
        assert result == ''

    def test_multiple_occurrences(self):
        """Берётся первое вхождение."""
        text = 'a first b a second b'
        result = self.extractor._extract_between(text, 'a', 'b')
        assert result == 'first'


# ===========================================================================
# _extract_city_from_address
# ===========================================================================


class TestExtractCityFromAddress:
    """Тесты для _extract_city_from_address()."""

    def setup_method(self):
        self.extractor = CompanyDataExtractor()

    def test_g_moscow(self):
        """Формат 'г. МОСКВА'."""
        result = self.extractor._extract_city_from_address(
            'г. МОСКВА, ул. Ленина'
        )
        assert result == 'Москва'

    def test_g_moscow_no_space(self):
        """Формат 'Г.МОСКВА'."""
        result = self.extractor._extract_city_from_address(
            'Г.МОСКВА, ул. Ленина'
        )
        assert result == 'Москва'

    def test_gorod(self):
        """Формат 'город Москва'."""
        result = self.extractor._extract_city_from_address(
            'город Москва, ул. Ленина'
        )
        assert result == 'Москва'

    def test_city_with_hyphen(self):
        """Город с дефисом."""
        result = self.extractor._extract_city_from_address(
            'г. Ростов-на-Дону, ул. Ленина'
        )
        assert result == 'Ростов-На-Дону'

    def test_no_city(self):
        """Без города."""
        result = self.extractor._extract_city_from_address('ул. Ленина, д. 1')
        assert result is None

    def test_empty_string(self):
        """Пустая строка."""
        result = self.extractor._extract_city_from_address('')
        assert result is None


# ===========================================================================
# _parse_raw_text
# ===========================================================================


class TestParseRawText:
    """Тесты для _parse_raw_text()."""

    def setup_method(self):
        self.extractor = CompanyDataExtractor()

    def test_full_parse(self):
        """Полный парсинг с датой, регионом и руководителем."""
        text = (
            'Адрес по данным ЕГРЮЛ\n'
            'г. МОСКВА, ул. Ленина, д. 1\n'
            'Дата регистрации\n'
            '15.01.2020\n'
            'Правовая форма (ОКОПФ)\n'
            'Общество с ограниченной ответственностью\n'
            'Единоличный исполнительный орган\n'
            'Иванов Иван Иванович\n'
            'ИНН\n'
            '1234567890\n'
            'Должность\n'
            'Генеральный директор\n'
            'Дата внесения данных в ЕГРЮЛ\n'
            '20.01.2020\n'
        )
        result = self.extractor._parse_raw_text(text)
        assert result['published_at'] == '15.01.2020'
        assert result['region'] == 'Москва'
        assert result['extra'] is not None
        assert 'Иванов Иван Иванович' in result['extra']

    def test_no_director_block(self):
        """Без блока руководителя."""
        text = (
            'Адрес по данным ЕГРЮЛ\n'
            'г. МОСКВА\n'
            'Дата регистрации\n'
            '15.01.2020\n'
            'Правовая форма (ОКОПФ)\n'
            'ООО\n'
        )
        result = self.extractor._parse_raw_text(text)
        assert result['published_at'] == '15.01.2020'
        assert result['region'] == 'Москва'
        assert result['extra'] is None

    def test_no_date(self):
        """Без даты регистрации (нет маркера 'Дата регистрации')."""
        text = 'Адрес по данным ЕГРЮЛ\nг. МОСКВА\nПравовая форма (ОКОПФ)\nООО\n'
        result = self.extractor._parse_raw_text(text)
        # Адрес есть, но end_marker "Дата регистрации" не найден,
        # поэтому _extract_between возвращает None
        assert result['published_at'] is None
        assert result['region'] is None
        assert result['extra'] is None

    def test_no_address(self):
        """Без адреса."""
        text = 'Дата регистрации\n15.01.2020\nПравовая форма (ОКОПФ)\nООО\n'
        result = self.extractor._parse_raw_text(text)
        assert result['published_at'] == '15.01.2020'
        assert result['region'] is None

    def test_empty_text(self):
        """Пустой текст."""
        result = self.extractor._parse_raw_text('')
        assert result['published_at'] is None
        assert result['region'] is None
        assert result['extra'] is None

    def test_invalid_date_format(self):
        """Дата не в формате DD.MM.YYYY."""
        text = 'Дата регистрации\n2020-01-15\nПравовая форма (ОКОПФ)\nООО\n'
        result = self.extractor._parse_raw_text(text)
        assert result['published_at'] is None


# ===========================================================================
# _extract_with_fallback
# ===========================================================================


@pytest.mark.asyncio
class TestExtractWithFallback:
    """Тесты для _extract_with_fallback() — требуют мока Page."""

    async def test_primary_success(self, mocker):
        """Основной селектор срабатывает через evaluate."""
        extractor = CompanyDataExtractor()
        mock_page = mocker.AsyncMock()
        mock_page.evaluate.return_value = 'Primary Text'

        result = await extractor._extract_with_fallback(
            mock_page, '.primary', '.fallback'
        )
        assert result == 'Primary Text'
        mock_page.evaluate.assert_called_once()

    async def test_primary_empty_fallback_success(self, mocker):
        """Основной селектор пуст, fallback срабатывает."""
        extractor = CompanyDataExtractor()
        mock_page = mocker.AsyncMock()
        # Первый evaluate (primary) возвращает пустую строку
        # Второй evaluate (fallback) возвращает текст
        mock_page.evaluate = mocker.AsyncMock(side_effect=['', 'Fallback Text'])

        result = await extractor._extract_with_fallback(
            mock_page, '.primary', '.fallback'
        )
        assert result == 'Fallback Text'

    async def test_all_empty(self, mocker):
        """Все селекторы пусты — возвращает None."""
        extractor = CompanyDataExtractor()
        mock_page = mocker.AsyncMock()
        mock_page.evaluate.return_value = ''

        # Явно мокаем locator().first, чтобы inner_text не создавал
        # невостребованный AsyncMock
        mock_first = mocker.AsyncMock(spec=['count', 'inner_text'])
        mock_first.count = mocker.AsyncMock(return_value=0)
        mock_locator = mocker.Mock()
        mock_locator.first = mock_first
        mock_page.locator.return_value = mock_locator

        result = await extractor._extract_with_fallback(
            mock_page, '.primary', '.fallback'
        )
        assert result is None

    async def test_no_fallback(self, mocker):
        """Без fallback-селектора."""
        extractor = CompanyDataExtractor()
        mock_page = mocker.AsyncMock()
        mock_page.evaluate.return_value = 'Only Primary'

        result = await extractor._extract_with_fallback(
            mock_page, '.primary', None
        )
        assert result == 'Only Primary'
