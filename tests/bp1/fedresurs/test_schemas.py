"""Тесты для schemas.py — SearchRequest, SearchResult, ProxyConfig, DirectorInfo."""  # noqa: E501

from datetime import datetime

from src.bp1.collectors.fedresurs_rpa.schemas import (
    DirectorInfo,
    ProxyConfig,
    SearchRequest,
    SearchResult,
)

# ===========================================================================
# ProxyConfig
# ===========================================================================


class TestProxyConfig:
    """Тесты для ProxyConfig."""

    def test_minimal(self):
        """Только server."""
        cfg = ProxyConfig(server='http://1.2.3.4:8080')
        assert cfg.server == 'http://1.2.3.4:8080'
        assert cfg.username is None
        assert cfg.password is None

    def test_with_auth(self):
        """С авторизацией."""
        cfg = ProxyConfig(
            server='http://1.2.3.4:8080', username='u', password='p'
        )
        assert cfg.username == 'u'
        assert cfg.password == 'p'


# ===========================================================================
# DirectorInfo
# ===========================================================================


class TestDirectorInfo:
    """Тесты для DirectorInfo."""

    def test_defaults(self):
        """Все поля None по умолчанию."""
        d = DirectorInfo()
        assert d.full_name is None
        assert d.inn is None
        assert d.position is None
        assert d.entry_date is None

    def test_full(self):
        """Все поля заполнены."""
        d = DirectorInfo(
            full_name='Иванов Иван',
            inn='1234567890',
            position='Генеральный директор',
            entry_date='01.01.2020',
        )
        assert d.full_name == 'Иванов Иван'
        assert d.inn == '1234567890'


# ===========================================================================
# SearchRequest
# ===========================================================================


class TestSearchRequest:
    """Тесты для SearchRequest."""

    def test_required_only(self):
        """Только обязательное поле name."""
        req = SearchRequest(name='ООО Тест')
        assert req.name == 'ООО Тест'
        assert req.inn is None
        assert req.proxy is None
        assert req.headless is None
        assert req.timeout == 60000
        assert req.retry_count == 3
        assert req.qrator_bypass is True

    def test_all_fields(self):
        """Все поля заполнены."""
        proxy = ProxyConfig(server='http://1.2.3.4:8080')
        req = SearchRequest(
            name='ООО Тест',
            inn='1234567890',
            proxy=proxy,
            user_agent='Custom UA',
            headless=False,
            output_dir='/tmp',
            timeout=30000,
            retry_count=5,
            qrator_bypass=False,
        )
        assert req.inn == '1234567890'
        assert req.proxy == proxy
        assert req.user_agent == 'Custom UA'
        assert req.headless is False
        assert req.timeout == 30000
        assert req.retry_count == 5
        assert req.qrator_bypass is False


# ===========================================================================
# SearchResult
# ===========================================================================


class TestSearchResult:
    """Тесты для SearchResult."""

    def test_success_minimal(self):
        """Успешный результат с минимальными полями."""
        result = SearchResult(success=True, name='ООО Тест')
        assert result.success is True
        assert result.name == 'ООО Тест'
        assert result.inn is None
        assert result.url is None
        assert result.status is None
        assert result.error is None

    def test_failure(self):
        """Результат с ошибкой."""
        result = SearchResult(
            success=False,
            name='ООО Тест',
            error='Connection failed',
            error_type='BrowserStartError',
        )
        assert result.success is False
        assert result.error == 'Connection failed'
        assert result.error_type == 'BrowserStartError'

    def test_full_success(self):
        """Полный успешный результат."""
        ts = datetime(2026, 8, 2, 12, 0, 0)
        result = SearchResult(
            success=True,
            name='ООО Тест',
            inn='1234567890',
            search_url='https://fedresurs.ru/search?q=test',
            timestamp=ts,
            url='https://fedresurs.ru/company/123',
            status='Действующее',
            raw_text='Полный текст компании',
            published_at='01.01.2020',
            region='Москва',
            extra='Иванов Иван\nИНН\n1234567890',
            file_path='/tmp/test.html',
            proxy_used='http://1.2.3.4:8080',
            user_agent_used='Mozilla/5.0',
        )
        assert result.inn == '1234567890'
        assert result.status == 'Действующее'
        assert result.region == 'Москва'
        assert result.file_path == '/tmp/test.html'

    # --- Properties ---

    def test_director_name(self):
        """director_name извлекается из extra."""
        result = SearchResult(
            success=True,
            name='Test',
            extra='Иванов Иван\nИНН\n1234567890',
        )
        assert result.director_name == 'Иванов Иван'

    def test_director_name_none(self):
        """director_name возвращает None если extra нет."""
        result = SearchResult(success=True, name='Test')
        assert result.director_name is None

    def test_director_inn(self):
        """director_inn извлекается из extra."""
        result = SearchResult(
            success=True,
            name='Test',
            extra='Иванов Иван\nИНН\n1234567890',
        )
        assert result.director_inn == '1234567890'

    def test_director_inn_none(self):
        """director_inn возвращает None если extra нет."""
        result = SearchResult(success=True, name='Test')
        assert result.director_inn is None

    def test_director_position(self):
        """director_position извлекается из extra."""
        result = SearchResult(
            success=True,
            name='Test',
            extra='Иванов Иван\nДолжность\nГенеральный директор',
        )
        assert result.director_position == 'Генеральный директор'

    def test_director_position_none(self):
        """director_position возвращает None если extra нет."""
        result = SearchResult(success=True, name='Test')
        assert result.director_position is None

    def test_director_date(self):
        """director_date извлекается из extra."""
        result = SearchResult(
            success=True,
            name='Test',
            extra=('Иванов Иван\nДата внесения данных в ЕГРЮЛ\n01.01.2020'),
        )
        assert result.director_date == '01.01.2020'

    def test_director_date_none(self):
        """director_date возвращает None если extra нет."""
        result = SearchResult(success=True, name='Test')
        assert result.director_date is None
