"""Тесты для network/pool.py — ProxyPool: автовыбор, кэш, cooldown."""

from typing import Any

from core.config import settings
from src.bp1.network.pool import ProxyPool, canonical_host
from src.bp1.network.provider import ProxyPort, UserBalance


class FakeRedis:
    """Redis в памяти — только то подмножество API, что использует ProxyPool."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class FakeSxOrgClient:
    """Заглушка провайдера — без сети, с журналом вызовов create_port."""

    def __init__(
        self,
        balance: float = 10.0,
        ports: list[ProxyPort] | None = None,
        created: list[ProxyPort] | None = None,
        free: list[str] | None = None,
        raise_on_balance: Exception | None = None,
        raise_on_search: Exception | None = None,
    ):
        self._balance = balance
        self._ports = ports or []
        self._created = created or []
        self._free = free or []
        self._raise_on_balance = raise_on_balance
        self._raise_on_search = raise_on_search
        self.create_port_calls: list[int] = []
        self.closed = False

    async def get_balance(self) -> UserBalance:
        if self._raise_on_balance:
            raise self._raise_on_balance
        return UserBalance(
            balance=self._balance,
            balance_traffic=0,
            all_available_traffic=0,
            prepared_traffic_balance=0,
            balance_hold=0,
        )

    async def get_ports(self, **kwargs: Any) -> list[ProxyPort]:
        return self._ports

    async def create_port(
        self, country_code: str, name: str, count: int = 1, **kwargs: Any
    ) -> list[ProxyPort]:
        self.create_port_calls.append(count)
        return self._created[:count]

    async def wait_for_port_ready(self, port_id: int, **kwargs: Any) -> bool:
        return True

    async def search_proxies(self, **kwargs: Any) -> list[str]:
        if self._raise_on_search:
            raise self._raise_on_search
        return self._free

    async def aclose(self) -> None:
        self.closed = True


def _port(id_: int, proxy: str) -> ProxyPort:
    return ProxyPort(
        id=id_,
        name=f'p{id_}',
        proxy=proxy,
        country='RU',
        city='',
        status=1,
        traffic_limit=0,
        used_traffic=0,
        created_at='',
    )


class TestCanonicalHost:
    """Тесты для canonical_host()."""

    def test_full_url_with_www(self):
        assert canonical_host('https://www.lenta.ru/news') == 'lenta.ru'

    def test_bare_domain(self):
        assert canonical_host('lenta.ru') == 'lenta.ru'

    def test_uppercase_and_trailing_slash(self):
        assert canonical_host('HTTPS://Example.COM/') == 'example.com'


class TestAutoSelectStrategy:
    """Автовыбор: баланс -> свои порты (создать при нехватке) / свободные."""

    async def test_sufficient_balance_and_ports_uses_own_ports(
        self, monkeypatch
    ):
        monkeypatch.setattr(settings, 'bp1_proxy_pool_size', 2)
        fake = FakeSxOrgClient(
            balance=10.0,
            ports=[_port(1, '1.1.1.1:1111'), _port(2, '2.2.2.2:2222')],
        )
        pool = ProxyPool(api_key='k', client_factory=lambda: fake)

        address = await pool.acquire('lenta.ru')

        assert address in ('http://1.1.1.1:1111', 'http://2.2.2.2:2222')
        assert fake.create_port_calls == []
        assert fake.closed is True

    async def test_sufficient_balance_creates_missing_ports(self):
        fake = FakeSxOrgClient(
            balance=10.0,
            ports=[_port(1, '1.1.1.1:1111')],
            created=[_port(2, '3.3.3.3:3333')],
        )
        pool = ProxyPool(api_key='k', client_factory=lambda: fake)

        # bp1_proxy_pool_size по умолчанию 20 -> не хватает 19 портов
        addresses = await pool._select_pool()

        assert 'http://1.1.1.1:1111' in addresses
        assert 'http://3.3.3.3:3333' in addresses
        assert fake.create_port_calls == [19]

    async def test_insufficient_balance_uses_free_proxies(self):
        fake = FakeSxOrgClient(
            balance=0.1, free=['5.5.5.5:5555', '6.6.6.6:6666']
        )
        pool = ProxyPool(api_key='k', client_factory=lambda: fake)

        addresses = await pool._select_pool()

        assert sorted(addresses) == [
            'http://5.5.5.5:5555',
            'http://6.6.6.6:6666',
        ]
        assert fake.create_port_calls == []


class TestDegradation:
    """Отказ провайдера -> acquire() возвращает None, не бросает исключение."""

    async def test_no_api_key_returns_none(self):
        pool = ProxyPool(api_key=None)
        assert await pool.acquire('lenta.ru') is None

    async def test_provider_error_returns_none(self):
        fake = FakeSxOrgClient(raise_on_balance=RuntimeError('provider down'))
        pool = ProxyPool(api_key='k', client_factory=lambda: fake)

        assert await pool.acquire('lenta.ru') is None


class TestPoolCaching:
    """Пул кэшируется в Redis — повторный acquire не бьёт в провайдера снова."""

    async def test_cached_pool_reused(self):
        calls = {'n': 0}

        def factory():
            calls['n'] += 1
            return FakeSxOrgClient(
                balance=10.0, ports=[_port(1, '1.1.1.1:1111')]
            )

        pool = ProxyPool(
            redis_client=FakeRedis(), api_key='k', client_factory=factory
        )

        await pool.acquire('lenta.ru')
        await pool.acquire('lenta.ru')

        assert calls['n'] == 1


class TestCooldown:
    """Прокси, заблокированный источником, не выбирается повторно для него."""

    async def test_blocked_address_skipped_for_same_source(self):
        fake = FakeSxOrgClient(balance=10.0, ports=[_port(1, '1.1.1.1:1111')])
        pool = ProxyPool(
            redis_client=FakeRedis(), api_key='k', client_factory=lambda: fake
        )

        address = await pool.acquire('lenta.ru')
        assert address == 'http://1.1.1.1:1111'

        await pool.mark_blocked('lenta.ru', address)

        assert await pool.acquire('lenta.ru') is None

    async def test_blocked_address_still_available_for_other_source(self):
        fake = FakeSxOrgClient(balance=10.0, ports=[_port(1, '1.1.1.1:1111')])
        pool = ProxyPool(
            redis_client=FakeRedis(), api_key='k', client_factory=lambda: fake
        )

        address = await pool.acquire('lenta.ru')
        await pool.mark_blocked('lenta.ru', address)

        assert await pool.acquire('kommersant.ru') == address


class TestCheckHealth:
    """check_health() — один реальный чек провайдера в начале прогона."""

    async def test_no_api_key_is_noop_success(self):
        pool = ProxyPool(redis_client=FakeRedis(), api_key=None)

        assert await pool.check_health() is True

    async def test_healthy_provider_returns_true_no_marker(self):
        fake = FakeSxOrgClient(balance=10.0)
        redis = FakeRedis()
        pool = ProxyPool(
            redis_client=redis, api_key='k', client_factory=lambda: fake
        )

        assert await pool.check_health() is True
        assert await redis.get('bp1:proxy:provider_down') is None
        assert fake.closed is True

    async def test_broken_provider_returns_false_and_sets_marker(self, caplog):
        fake = FakeSxOrgClient(raise_on_balance=RuntimeError('invalid api key'))
        redis = FakeRedis()
        pool = ProxyPool(
            redis_client=redis, api_key='k', client_factory=lambda: fake
        )

        with caplog.at_level('WARNING'):
            result = await pool.check_health()

        assert result is False
        assert await redis.get('bp1:proxy:provider_down') is not None
        assert (
            sum('Прокси не работает' in r.message for r in caplog.records) == 1
        )

    async def test_search_proxies_failure_marks_unhealthy(self, caplog):
        # Реальный случай: get_balance() успешен (ключ валиден), баланс
        # ниже порога -> ветка search_proxies(), а она отдельно отказывает
        # (sx.org: HTTP 400 "Insufficient funds..."). check_health() должен
        # поймать и это, не только сбой get_balance().
        fake = FakeSxOrgClient(
            balance=0.0, raise_on_search=RuntimeError('insufficient funds')
        )
        redis = FakeRedis()
        pool = ProxyPool(
            redis_client=redis, api_key='k', client_factory=lambda: fake
        )

        with caplog.at_level('WARNING'):
            result = await pool.check_health()

        assert result is False
        assert await redis.get('bp1:proxy:provider_down') is not None

    async def test_healthy_check_pre_warms_pool_cache(self):
        calls = {'n': 0}

        def factory():
            calls['n'] += 1
            return FakeSxOrgClient(
                balance=10.0, ports=[_port(1, '1.1.1.1:1111')]
            )

        redis = FakeRedis()
        pool = ProxyPool(
            redis_client=redis, api_key='k', client_factory=factory
        )

        assert await pool.check_health() is True
        assert calls['n'] == 1

        # acquire() сразу после check_health() не должен снова бить в
        # провайдера — пул уже закэширован.
        address = await pool.acquire('lenta.ru')
        assert address == 'http://1.1.1.1:1111'
        assert calls['n'] == 1

    async def test_clears_marker_after_recovery(self):
        redis = FakeRedis()
        await redis.set('bp1:proxy:provider_down', 'invalid api key')
        fake = FakeSxOrgClient(balance=10.0)
        pool = ProxyPool(
            redis_client=redis, api_key='k', client_factory=lambda: fake
        )

        assert await pool.check_health() is True
        assert await redis.get('bp1:proxy:provider_down') is None

    async def test_marked_down_provider_skips_further_provider_calls(self):
        calls = {'n': 0}

        def factory():
            calls['n'] += 1
            return FakeSxOrgClient(
                raise_on_balance=RuntimeError('invalid api key')
            )

        redis = FakeRedis()
        pool = ProxyPool(
            redis_client=redis, api_key='k', client_factory=factory
        )

        await pool.check_health()
        assert calls['n'] == 1

        # acquire() в рамках того же прогона не должен снова обращаться
        # к провайдеру — маркер уже стоит.
        assert await pool.acquire('lenta.ru') is None
        assert await pool.acquire('kommersant.ru') is None
        assert calls['n'] == 1
