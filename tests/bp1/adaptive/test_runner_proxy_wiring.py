"""Тесты для AdaptiveRunner._get_parser_for_source() — прокси для
классического RPA-контура (fedresurs.ru).

Проверяет, что уже существующая, но раньше не заполнявшаяся проводка
(``FedresursAdapter.proxy`` / ``BrowserManager._build_proxy_dict``)
наконец получает значение из ``network/pool.py`` (изменение
``add-rpa-collection-proxying``).
"""

from src.bp1.adaptive.integration.runner import AdaptiveRunner
from src.bp1.collectors.fedresurs_rpa.schemas import ProxyConfig
from src.bp1.parsers.fedresurs_adapter import FedresursAdapter


class TestGetParserForSourceProxy:
    """Прокси из пула пробрасывается в специализированный RPA-парсер."""

    async def test_wraps_acquired_proxy_into_proxy_config(self, mocker):
        runner = AdaptiveRunner()
        mocker.patch.object(
            runner._proxy_pool,
            'acquire',
            return_value='http://1.2.3.4:8080',
        )

        parser = await runner._get_parser_for_source('fedresurs.ru')

        assert isinstance(parser, FedresursAdapter)
        assert parser._proxy == ProxyConfig(server='http://1.2.3.4:8080')

    async def test_no_proxy_available_still_returns_parser(self, mocker):
        runner = AdaptiveRunner()
        mocker.patch.object(runner._proxy_pool, 'acquire', return_value=None)

        parser = await runner._get_parser_for_source('fedresurs.ru')

        assert isinstance(parser, FedresursAdapter)
        assert parser._proxy is None

    async def test_unregistered_source_returns_none_without_proxy_lookup(
        self, mocker
    ):
        runner = AdaptiveRunner()
        acquire_mock = mocker.patch.object(runner._proxy_pool, 'acquire')

        parser = await runner._get_parser_for_source('unknown-source.example')

        assert parser is None
        acquire_mock.assert_not_called()
