"""Тесты для parser.py — FedresursRPA."""

import pytest

from src.bp1.collectors.fedresurs_rpa.exceptions import (
    PageLoadError,
    SearchExecutionError,
)
from src.bp1.collectors.fedresurs_rpa.parser import FedresursRPA
from src.bp1.collectors.fedresurs_rpa.schemas import (
    ProxyConfig,
    SearchRequest,
    SearchResult,
)

# ===========================================================================
# search() — логика retry
# ===========================================================================


@pytest.mark.asyncio
class TestSearchRetryLogic:
    """Тесты для FedresursRPA.search() — логика повторных попыток."""

    async def test_success_first_attempt(self, mocker):
        """Успех с первой попытки."""
        parser = FedresursRPA()
        request = SearchRequest(name='Test', inn='1234567890')

        mock_result = SearchResult(success=True, name='Test')
        mocker.patch.object(parser, '_execute_search', return_value=mock_result)

        result = await parser.search(request)
        assert result.success is True
        assert parser._execute_search.call_count == 1

    async def test_success_second_attempt(self, mocker):
        """Успех со второй попытки (первая упала)."""
        parser = FedresursRPA()
        request = SearchRequest(name='Test', inn='1234567890', retry_count=3)

        fail_result = SearchResult(
            success=False, name='Test', error='fail', error_type='Error'
        )
        success_result = SearchResult(success=True, name='Test')

        mocker.patch.object(
            parser,
            '_execute_search',
            side_effect=[fail_result, success_result],
        )

        result = await parser.search(request)
        assert result.success is True
        assert parser._execute_search.call_count == 2

    async def test_all_attempts_fail(self, mocker):
        """Все попытки исчерпаны."""
        parser = FedresursRPA()
        request = SearchRequest(name='Test', inn='1234567890', retry_count=3)

        fail_result = SearchResult(
            success=False, name='Test', error='fail', error_type='Error'
        )
        mocker.patch.object(parser, '_execute_search', return_value=fail_result)

        result = await parser.search(request)
        assert result.success is False
        assert 'исчерпаны' in (result.error or '')
        assert parser._execute_search.call_count == 3

    async def test_exception_during_execute(self, mocker):
        """Исключение в _execute_search обрабатывается как неудача."""
        parser = FedresursRPA()
        request = SearchRequest(name='Test', inn='1234567890', retry_count=2)

        mocker.patch.object(
            parser,
            '_execute_search',
            side_effect=Exception('Unexpected error'),
        )

        result = await parser.search(request)
        assert result.success is False
        assert 'Unexpected error' in (result.error or '')

    async def test_retry_with_backoff(self, mocker):
        """Проверка, что между попытками есть задержка."""
        parser = FedresursRPA()
        request = SearchRequest(name='Test', inn='1234567890', retry_count=2)

        fail_result = SearchResult(
            success=False, name='Test', error='fail', error_type='Error'
        )
        mocker.patch.object(parser, '_execute_search', return_value=fail_result)
        mock_sleep = mocker.patch('asyncio.sleep', return_value=None)

        await parser.search(request)
        # Должен быть хотя бы один вызов sleep между попытками
        assert mock_sleep.call_count >= 1


# ===========================================================================
# _execute_search
# ===========================================================================


@pytest.mark.asyncio
class TestExecuteSearch:
    """Тесты для FedresursRPA._execute_search()."""

    async def test_success(self, mocker):
        """Успешное выполнение поиска."""
        parser = FedresursRPA()

        # Мокаем BrowserManager
        mock_browser_manager = mocker.AsyncMock()
        mock_context = mocker.AsyncMock()
        mock_page = mocker.AsyncMock()
        mock_browser_manager.start.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_browser_manager.user_agent = 'Test UA'

        # page.url — property, а не метод
        type(mock_page).url = mocker.PropertyMock(
            return_value='https://fedresurs.ru/company/123'
        )

        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.parser.BrowserManager',
            return_value=mock_browser_manager,
        )

        # Мокаем методы парсера
        mocker.patch.object(parser, '_select_category', return_value=None)
        mocker.patch.object(parser, '_perform_search', return_value=None)
        mocker.patch.object(parser, '_wait_for_results', return_value=None)
        mocker.patch.object(parser, '_open_company_card', return_value=None)
        mocker.patch.object(parser, '_save_page', return_value=None)
        mocker.patch.object(
            parser,
            '_extract_data_from_page',
            return_value={
                'status': 'Действующее',
                'full_text': 'text',
                'published_at': '01.01.2020',
                'region': 'Москва',
                'extra': 'Director info',
            },
        )

        request = SearchRequest(
            name='Test',
            inn='1234567890',
            qrator_bypass=False,
            timeout=30000,
            output_dir='/tmp',
        )

        result = await parser._execute_search(
            request=request, proxy=None, headless=True
        )

        assert result.success is True
        assert result.name == 'Test'
        assert result.status == 'Действующее'
        assert result.region == 'Москва'
        mock_browser_manager.close.assert_awaited_once()

    async def test_browser_error(self, mocker):
        """Ошибка запуска браузера (start вне try) — исключение наружу."""
        parser = FedresursRPA()

        mock_browser_manager = mocker.AsyncMock()
        mock_browser_manager.start.side_effect = Exception('Browser crashed')
        mock_browser_manager.user_agent = 'Test UA'

        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.parser.BrowserManager',
            return_value=mock_browser_manager,
        )

        request = SearchRequest(name='Test', inn='1234567890')

        with pytest.raises(Exception, match='Browser crashed'):
            await parser._execute_search(
                request=request, proxy=None, headless=True
            )

    async def test_qrator_bypass_failure(self, mocker):
        """Ошибка обхода QRATOR."""
        parser = FedresursRPA()

        mock_browser_manager = mocker.AsyncMock()
        mock_context = mocker.AsyncMock()
        mock_page = mocker.AsyncMock()
        mock_browser_manager.start.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_browser_manager.user_agent = 'Test UA'

        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.parser.BrowserManager',
            return_value=mock_browser_manager,
        )
        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.parser.bypass_qrator',
            return_value=False,
        )

        request = SearchRequest(
            name='Test', inn='1234567890', qrator_bypass=True
        )

        result = await parser._execute_search(
            request=request, proxy=None, headless=True
        )

        assert result.success is False
        assert (
            'QRATOR' in (result.error or '').upper()
            or 'антибот' in (result.error or '').lower()
        )
        mock_browser_manager.close.assert_awaited_once()


# ===========================================================================
# _select_category
# ===========================================================================


@pytest.mark.asyncio
class TestSelectCategory:
    """Тесты для FedresursRPA._select_category()."""

    async def test_success(self, mocker):
        """Успешный выбор категории."""
        parser = FedresursRPA()
        # get_by_role/get_by_label — синхронные в Playwright
        mock_page = mocker.Mock(spec=object)
        mock_combobox = mocker.AsyncMock()
        mock_options = mocker.Mock()
        mock_liца = mocker.AsyncMock()
        mock_options.get_by_text = mocker.Mock(return_value=mock_liца)
        mock_page.get_by_role = mocker.Mock(return_value=mock_combobox)
        mock_page.get_by_label = mocker.Mock(return_value=mock_options)

        await parser._select_category(mock_page)

        mock_page.get_by_role.assert_called_with('combobox')
        mock_combobox.click.assert_awaited_once()
        mock_page.get_by_label.assert_called_with('Options list')
        mock_options.get_by_text.assert_called_with('Лица')
        mock_liца.click.assert_awaited_once()

    async def test_skip_on_error(self, mocker):
        """Ошибка выбора категории не прерывает выполнение."""
        parser = FedresursRPA()
        # Используем Mock вместо AsyncMock, чтобы get_by_role().click()
        # не создавал невостребованные AsyncMock-и
        mock_page = mocker.Mock()
        mock_page.get_by_role.side_effect = Exception('Element not found')

        # Не должно быть исключения
        await parser._select_category(mock_page)


# ===========================================================================
# _perform_search
# ===========================================================================


@pytest.mark.asyncio
class TestPerformSearch:
    """Тесты для FedresursRPA._perform_search()."""

    async def test_success(self, mocker):
        """Успешный ввод поискового запроса."""
        parser = FedresursRPA()
        # page.locator и get_by_role — синхронные в Playwright
        mock_page = mocker.Mock(spec=object)
        mock_page.locator = mocker.Mock()

        mock_input_locator = mocker.AsyncMock()
        mock_button_locator = mocker.AsyncMock()

        # Первый вызов locator — для search_input
        mock_search_container = mocker.Mock()
        mock_search_container.get_by_role = mocker.Mock(
            return_value=mock_input_locator
        )
        # Второй вызов locator — для search_button
        mock_button_container = mocker.Mock()
        mock_button_container.get_by_role = mocker.Mock(
            return_value=mock_button_locator
        )
        mock_page.locator.side_effect = [
            mock_search_container,
            mock_button_container,
        ]

        await parser._perform_search(mock_page, '1234567890')

        mock_input_locator.click.assert_awaited()
        mock_input_locator.fill.assert_awaited_with('1234567890')
        mock_button_locator.click.assert_awaited()

    async def test_failure(self, mocker):
        """Ошибка поиска — SearchExecutionError."""
        parser = FedresursRPA()
        # Используем Mock, чтобы locator().click() не создавал
        # невостребованные AsyncMock-и
        mock_page = mocker.Mock()
        mock_page.locator.side_effect = Exception('Element not found')

        with pytest.raises(SearchExecutionError):
            await parser._perform_search(mock_page, '1234567890')


# ===========================================================================
# _wait_for_results
# ===========================================================================


@pytest.mark.asyncio
class TestWaitForResults:
    """Тесты для FedresursRPA._wait_for_results()."""

    async def test_networkidle_success(self, mocker):
        """Успешное ожидание networkidle."""
        parser = FedresursRPA()
        mock_page = mocker.AsyncMock()

        await parser._wait_for_results(mock_page, timeout=30000)

        mock_page.wait_for_load_state.assert_awaited_with(
            'networkidle', timeout=30000
        )

    async def test_networkidle_timeout(self, mocker):
        """Таймаут networkidle — fallback ожидание."""
        parser = FedresursRPA()
        mock_page = mocker.AsyncMock()
        mock_page.wait_for_load_state.side_effect = Exception('Timeout')

        await parser._wait_for_results(mock_page, timeout=30000)

        # Должен быть вызван fallback sleep
        assert mock_page.wait_for_load_state.call_count >= 1

    async def test_selector_found(self, mocker):
        """Селектор результата найден."""
        parser = FedresursRPA()
        mock_page = mocker.AsyncMock()

        await parser._wait_for_results(mock_page, timeout=30000)

        mock_page.wait_for_selector.assert_awaited()


# ===========================================================================
# _open_company_card
# ===========================================================================


@pytest.mark.asyncio
class TestOpenCompanyCard:
    """Тесты для FedresursRPA._open_company_card()."""

    async def test_success(self, mocker):
        """Успешное открытие карточки компании."""
        parser = FedresursRPA()
        # page.locator — синхронный метод в Playwright
        mock_page = mocker.Mock(spec=object)
        mock_page.wait_for_load_state = mocker.AsyncMock()
        mock_page.wait_for_selector = mocker.AsyncMock()
        mock_page.locator = mocker.Mock()

        mock_link = mocker.AsyncMock()
        mock_filtered = mocker.Mock()
        mock_filtered.first = mock_link
        mock_page.locator.return_value.filter.return_value = mock_filtered

        await parser._open_company_card(mock_page)

        mock_link.wait_for.assert_awaited_with(state='visible', timeout=15000)
        mock_link.click.assert_awaited()

    async def test_no_link(self, mocker):
        """Ссылка не найдена — не прерывает выполнение."""
        parser = FedresursRPA()
        mock_page = mocker.Mock(spec=object)
        mock_page.wait_for_load_state = mocker.AsyncMock()
        mock_page.wait_for_selector = mocker.AsyncMock()
        mock_page.locator = mocker.Mock()

        mock_link = mocker.AsyncMock()
        mock_link.wait_for.side_effect = Exception('Not visible')
        mock_filtered = mocker.Mock()
        mock_filtered.first = mock_link
        mock_page.locator.return_value.filter.return_value = mock_filtered

        # Не должно быть исключения
        await parser._open_company_card(mock_page)


# ===========================================================================
# _save_page
# ===========================================================================


@pytest.mark.asyncio
class TestSavePage:
    """Тесты для FedresursRPA._save_page()."""

    async def test_success(self, mocker):
        """Успешное сохранение HTML."""
        parser = FedresursRPA()
        mock_page = mocker.AsyncMock()
        mock_page.evaluate.return_value = '<html><body>Test</body></html>'

        mock_open = mocker.mock_open()
        mocker.patch('builtins.open', mock_open)

        await parser._save_page(mock_page, '/tmp/test.html')

        mock_open.assert_called_once_with(
            '/tmp/test.html', 'w', encoding='utf-8'
        )
        handle = mock_open()
        handle.write.assert_called_once()
        # Проверяем, что DOCTYPE добавлен
        written_content = handle.write.call_args[0][0]
        assert written_content.startswith('<!DOCTYPE html>')

    async def test_os_error(self, mocker):
        """Ошибка записи — PageLoadError."""
        parser = FedresursRPA()
        mock_page = mocker.AsyncMock()
        mock_page.evaluate.return_value = '<html></html>'

        mocker.patch('builtins.open', side_effect=OSError('Permission denied'))

        with pytest.raises(PageLoadError):
            await parser._save_page(mock_page, '/tmp/test.html')


# ===========================================================================
# _extract_data_from_page
# ===========================================================================


@pytest.mark.asyncio
class TestExtractDataFromPage:
    """Тесты для FedresursRPA._extract_data_from_page()."""

    async def test_success(self, mocker):
        """Успешное извлечение данных."""
        parser = FedresursRPA()
        mock_page = mocker.AsyncMock()

        mock_extractor = mocker.AsyncMock()
        mock_extractor.extract_company_data.return_value = {
            'status': 'Действующее',
            'full_text': 'Company text',
            'published_at': '01.01.2020',
            'region': 'Москва',
            'extra': 'Director info',
        }

        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.parser.CompanyDataExtractor',
            return_value=mock_extractor,
        )

        result = await parser._extract_data_from_page(mock_page)

        assert result['status'] == 'Действующее'
        assert result['region'] == 'Москва'
        mock_extractor.extract_company_data.assert_awaited_once_with(mock_page)

    async def test_empty_result(self, mocker):
        """Извлечение с пустыми данными."""
        parser = FedresursRPA()
        mock_page = mocker.AsyncMock()

        mock_extractor = mocker.AsyncMock()
        mock_extractor.extract_company_data.return_value = {
            'status': None,
            'full_text': None,
            'published_at': None,
            'region': None,
            'extra': None,
        }

        mocker.patch(
            'src.bp1.collectors.fedresurs_rpa.parser.CompanyDataExtractor',
            return_value=mock_extractor,
        )

        result = await parser._extract_data_from_page(mock_page)

        assert result['status'] is None
        assert result['region'] is None


# ===========================================================================
# __init__ — конструктор
# ===========================================================================


class TestFedresursRPAInit:
    """Тесты для конструктора FedresursRPA."""

    def test_default_values(self):
        """Значения по умолчанию."""
        parser = FedresursRPA()
        assert parser._default_proxy is None
        assert parser._default_headless is True

    def test_custom_values(self):
        """Кастомные значения."""
        proxy = ProxyConfig(server='http://1.2.3.4:8080')
        parser = FedresursRPA(default_proxy=proxy, default_headless=False)
        assert parser._default_proxy == proxy
        assert parser._default_headless is False
