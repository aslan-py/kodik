"""Тесты кэша фида и раннего выхода из ``AdaptiveParser.parse()``
(design.md изменения add-rss-sitemap-collection, D4/D5)."""

import pytest

from core.config import settings
from src.bp1.adaptive.processing.feed import DiscoveredFeed
from src.bp1.adaptive.processing.parser import AdaptiveParser
from src.bp1.adaptive.schemas import StrategyResult, StrategyType

from .constants import COMPETITOR

_CORE_MODULE = 'src.bp1.adaptive.processing.parser.core'

_VALID_RSS = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    '<item><title>Новость</title><link>https://lenta.ru/1</link>'
    '<description>Текст</description></item>'
    '</channel></rss>'
)

_HTML_WITH_LINKS = """
<html>
<body>
  <a href="https://example.com/news/1">Новость про ИИ</a>
  <a href="https://example.com/news/2">Новость про нейросети</a>
</body>
</html>
"""


class FakeRedis:
    """Redis в памяти — то же подмножество API, что и в test_pool.py."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _FakeOrchestrator:
    async def fetch_with_degradation(self, url: str, **kwargs):
        return StrategyResult(
            strategy=StrategyType.FAST,
            success=True,
            data=_HTML_WITH_LINKS,
            content_length=len(_HTML_WITH_LINKS),
        )


class _AssertNotCalledOrchestrator:
    async def fetch_with_degradation(self, url: str, **kwargs):
        raise AssertionError(
            'HTML-лестница деградации не должна вызываться, если фид '
            'сработал (design.md D4)'
        )


def _feed_found(*_args, **_kwargs) -> DiscoveredFeed:
    return DiscoveredFeed(
        url='https://lenta.ru/rss', kind='rss', raw_body=_VALID_RSS
    )


async def _no_feed(*_args, **_kwargs) -> None:
    return None


class TestFeedMaterialsCache:
    @pytest.mark.asyncio
    async def test_materials_cache_hit_skips_rediscovery(self, monkeypatch):
        parser = AdaptiveParser()
        parser.bind_redis(FakeRedis())
        calls = {'n': 0}

        async def counting_discover(*args, **kwargs):
            calls['n'] += 1
            return _feed_found()

        monkeypatch.setattr(
            f'{_CORE_MODULE}.discover_feed_async', counting_discover
        )

        first = await parser._get_feed_materials('lenta.ru', 'https://lenta.ru')
        second = await parser._get_feed_materials(
            'lenta.ru', 'https://lenta.ru'
        )

        assert first
        assert second == first
        assert calls['n'] == 1

    @pytest.mark.asyncio
    async def test_single_failure_keeps_discovery_cached(self, monkeypatch):
        parser = AdaptiveParser()
        redis = FakeRedis()
        parser.bind_redis(redis)
        monkeypatch.setattr(
            f'{_CORE_MODULE}.discover_feed_async', _feed_found_async
        )

        materials = await parser._get_feed_materials(
            'lenta.ru', 'https://lenta.ru'
        )
        assert materials

        # Симулируем истечение TTL кэша материалов (в FakeRedis TTL не
        # применяется) — удаляем ключ материалов напрямую, как это сделал
        # бы Redis по истечении bp1_feed_items_cache_ttl_seconds.
        await redis.delete(parser._cache._feed_materials_key('lenta.ru'))

        async def failing_fetch(_url: str) -> str:
            raise RuntimeError('источник временно недоступен')

        monkeypatch.setattr(
            f'{_CORE_MODULE}.fetch_feed_body_async', failing_fetch
        )

        result = await parser._get_feed_materials(
            'lenta.ru', 'https://lenta.ru'
        )
        assert result is None

        discovery = await parser._cache.get_feed_discovery('lenta.ru')
        assert discovery is not None
        assert discovery.feed_url == 'https://lenta.ru/rss'
        assert discovery.fail_count == 1

    @pytest.mark.asyncio
    async def test_two_failures_in_a_row_clear_discovery(self, monkeypatch):
        parser = AdaptiveParser()
        redis = FakeRedis()
        parser.bind_redis(redis)
        monkeypatch.setattr(
            f'{_CORE_MODULE}.discover_feed_async', _feed_found_async
        )

        materials = await parser._get_feed_materials(
            'lenta.ru', 'https://lenta.ru'
        )
        assert materials

        async def failing_fetch(_url: str) -> str:
            raise RuntimeError('источник временно недоступен')

        monkeypatch.setattr(
            f'{_CORE_MODULE}.fetch_feed_body_async', failing_fetch
        )

        await redis.delete(parser._cache._feed_materials_key('lenta.ru'))
        assert (
            await parser._get_feed_materials('lenta.ru', 'https://lenta.ru')
            is None
        )

        await redis.delete(parser._cache._feed_materials_key('lenta.ru'))
        assert (
            await parser._get_feed_materials('lenta.ru', 'https://lenta.ru')
            is None
        )

        assert await parser._cache.get_feed_discovery('lenta.ru') is None

    @pytest.mark.asyncio
    async def test_no_feed_discovered_caches_negative_result(self, monkeypatch):
        parser = AdaptiveParser()
        parser.bind_redis(FakeRedis())
        calls = {'n': 0}

        async def counting_no_feed(*args, **kwargs):
            calls['n'] += 1
            return None

        monkeypatch.setattr(
            f'{_CORE_MODULE}.discover_feed_async', counting_no_feed
        )

        first = await parser._get_feed_materials('lenta.ru', 'https://lenta.ru')
        second = await parser._get_feed_materials(
            'lenta.ru', 'https://lenta.ru'
        )

        assert first is None
        assert second is None
        # Отрицательный результат тоже кэшируется — второй вызов не
        # пере-пробует конвенциональные пути (specs/bp1/
        # rss-sitemap-collection/spec.md, «Кэширование обнаруженного
        # фида на источник»).
        assert calls['n'] == 1


async def _feed_found_async(*args, **kwargs) -> DiscoveredFeed:
    return _feed_found()


class TestEarlyFeedExitInParse:
    @pytest.mark.asyncio
    async def test_news_source_with_feed_skips_html_ladder(self, monkeypatch):
        monkeypatch.setattr(settings, 'llm_api_key', None)
        monkeypatch.setattr(
            f'{_CORE_MODULE}.discover_feed_async', _feed_found_async
        )
        parser = AdaptiveParser()
        parser._orchestrator = _AssertNotCalledOrchestrator()

        result = await parser.parse(
            url='https://lenta.ru/search?q=x',
            source_name='lenta.ru',
            competitor=COMPETITOR,
        )

        assert result.status == 'ok'
        assert result.strategy_used == StrategyType.FEED
        assert result.items[0]['extra']['news']

    @pytest.mark.asyncio
    async def test_news_source_without_feed_falls_back_to_html(
        self, monkeypatch
    ):
        monkeypatch.setattr(settings, 'llm_api_key', None)
        monkeypatch.setattr(f'{_CORE_MODULE}.discover_feed_async', _no_feed)
        parser = AdaptiveParser()
        parser._orchestrator = _FakeOrchestrator()

        result = await parser.parse(
            url='https://lenta.ru/search?q=x',
            source_name='lenta.ru',
            competitor=COMPETITOR,
        )

        assert result.status == 'ok'
        assert result.strategy_used == StrategyType.FAST

    @pytest.mark.asyncio
    async def test_non_news_source_never_attempts_discovery(self, monkeypatch):
        monkeypatch.setattr(settings, 'llm_api_key', None)

        async def failing_discover(*args, **kwargs):
            raise AssertionError(
                'обнаружение фида не должно вызываться для '
                'не-новостных источников'
            )

        monkeypatch.setattr(
            f'{_CORE_MODULE}.discover_feed_async', failing_discover
        )
        parser = AdaptiveParser()
        parser._orchestrator = _FakeOrchestrator()

        result = await parser.parse(
            url='https://api.hh.ru/vacancies',
            source_name='api.hh.ru',
            competitor=COMPETITOR,
        )

        assert result.status == 'ok'
        assert result.strategy_used == StrategyType.FAST
