"""Тесты для network/provider.py — SxOrgClient на httpx.AsyncClient.

Сеть не используется — транспорт httpx подменён на ``MockTransport``.
"""

from collections.abc import Callable

import httpx
import pytest

from src.bp1.network.provider import (
    ProxyPort,
    SxOrgClient,
    UserBalance,
    format_proxy_string,
)

_BALANCE_PAYLOAD = {
    'balance': '12.41',
    'balance_traffic': '0',
    'all_available_traffic': '5',
    'prepared_traffic_balance': '0',
    'balance_hold': '0',
}


def _client_with_handler(
    handler: Callable[[httpx.Request], httpx.Response],
) -> SxOrgClient:
    """Создать SxOrgClient с подменённым транспортом (без сети)."""
    client = SxOrgClient(api_key='test-key')
    client._client = httpx.AsyncClient(
        base_url=client._client.base_url,
        transport=httpx.MockTransport(handler),
    )
    return client


class TestGetBalance:
    """Тесты для get_balance()."""

    async def test_returns_balance(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == '/v2/user/balance'
            assert request.url.params['apiKey'] == 'test-key'
            return httpx.Response(200, json=_BALANCE_PAYLOAD)

        client = _client_with_handler(handler)
        balance = await client.get_balance()

        assert isinstance(balance, UserBalance)
        assert balance.balance == 12.41
        assert balance.all_available_traffic == 5.0


class TestGetPorts:
    """Тесты для get_ports() — разбор вложенного message.data."""

    async def test_parses_nested_message_data(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    'message': {
                        'data': [
                            {
                                'id': 1,
                                'name': 'p1',
                                'proxy': '1.2.3.4:8080',
                                'status': 1,
                            }
                        ]
                    }
                },
            )

        client = _client_with_handler(handler)
        ports = await client.get_ports()

        assert len(ports) == 1
        assert isinstance(ports[0], ProxyPort)
        assert ports[0].proxy == '1.2.3.4:8080'
        assert ports[0].status == 1

    async def test_empty_result(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={'message': {'data': []}})

        client = _client_with_handler(handler)
        ports = await client.get_ports()

        assert ports == []


class TestCreatePort:
    """Тесты для create_port()."""

    async def test_creates_ports(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == 'POST'
            return httpx.Response(
                200,
                json={
                    'data': [
                        {
                            'id': 5,
                            'name': 'Auto_1',
                            'proxy': '5.6.7.8:9090',
                            'status': 1,
                        }
                    ]
                },
            )

        client = _client_with_handler(handler)
        ports = await client.create_port(country_code='RU', name='Auto_1')

        assert len(ports) == 1
        assert ports[0].id == 5


class TestSearchProxies:
    """Тесты для search_proxies() — свободные (бесплатные) прокси."""

    async def test_returns_ip_port_strings(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    'success': True,
                    'proxy1': '1.1.1.1:1111',
                    'proxy2': '2.2.2.2:2222',
                    'message': 'ignored',
                },
            )

        client = _client_with_handler(handler)
        proxies = await client.search_proxies(country='RU', limit=10)

        assert sorted(proxies) == ['1.1.1.1:1111', '2.2.2.2:2222']


class TestApiErrorHandling:
    """Ошибка на уровне полезной нагрузки (success: false) не ретраится."""

    async def test_success_false_raises_without_retry(self, mocker):
        sleep_mock = mocker.patch('src.bp1.network.provider.asyncio.sleep')
        calls = {'n': 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls['n'] += 1
            return httpx.Response(
                200, json={'success': False, 'error': 'bad key'}
            )

        client = _client_with_handler(handler)
        with pytest.raises(ValueError, match='bad key'):
            await client.get_balance()

        assert calls['n'] == 1
        sleep_mock.assert_not_called()


class TestRetryOnHttpError:
    """Сетевая ошибка ретраится с экспоненциальным бэкоффом."""

    async def test_retries_then_succeeds(self, mocker):
        mocker.patch('src.bp1.network.provider.asyncio.sleep')
        calls = {'n': 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls['n'] += 1
            if calls['n'] < 3:
                raise httpx.ConnectError('boom', request=request)
            return httpx.Response(200, json=_BALANCE_PAYLOAD)

        client = _client_with_handler(handler)
        balance = await client.get_balance()

        assert calls['n'] == 3
        assert balance.balance == 12.41

    async def test_gives_up_after_max_retries(self, mocker):
        mocker.patch('src.bp1.network.provider.asyncio.sleep')

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError('boom', request=request)

        client = _client_with_handler(handler)
        client._max_retries = 1

        with pytest.raises(httpx.ConnectError):
            await client.get_balance()


class TestFormatProxyString:
    """Тесты для format_proxy_string() — чистая функция."""

    def test_with_credentials(self):
        result = format_proxy_string(
            '1.2.3.4', 8080, username='u', password='p'
        )
        assert result == 'http://u:p@1.2.3.4:8080'

    def test_without_credentials(self):
        result = format_proxy_string('1.2.3.4', 8080)
        assert result == 'http://1.2.3.4:8080'

    def test_custom_protocol(self):
        result = format_proxy_string('1.2.3.4', 1080, protocol='socks5')
        assert result == 'socks5://1.2.3.4:1080'
