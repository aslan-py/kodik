"""Интеграционные тесты для адаптивного пакета."""

import pytest

from src.bp1.adaptive.core.cache import UnifiedCache
from src.bp1.adaptive.integration.bridge import AdaptiveBridgeParser
from src.bp1.adaptive.schemas import AdapterState, StrategyResult, StrategyType
from src.bp1.adaptive.strategies.hitl import HITLManager

from .constants import (
    ADAPTER_CONFIDENCE,
    COMPETITOR,
    EXAMPLE_SOURCE_NAME,
    EXAMPLE_URL,
    PARSER_TYPE_ADAPTIVE,
    SEARCH_TASK_ID,
    TITLE_FIELD,
    TITLE_SELECTOR,
    TRIGGER,
)

_HTML = """
<html>
<body>
  <a href="https://example.com/news/1">Новость про ИИ</a>
</body>
</html>
"""


class _FakeOrchestrator:
    """Оркестратор-заглушка."""

    async def fetch_with_degradation(self, url: str, **kwargs):
        return StrategyResult(
            strategy=StrategyType.FAST,
            success=True,
            data=_HTML,
            content_length=len(_HTML),
        )


class _FakeRedis:
    """Фейковый Redis-клиент для тестов."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)

    async def exists(self, key: str):
        return key in self._store

    async def incr(self, key: str):
        new_value = int(self._store.get(key, 0)) + 1
        self._store[key] = str(new_value)
        return new_value


@pytest.mark.asyncio
async def test_bridge_returns_parsed_response(monkeypatch):
    """AdaptiveBridgeParser возвращает ParsedResponse."""
    # Очищаем ключи LLM, чтобы использовалась эвристика (сбор ссылок),
    # а не реальный LLM-путь (не зависеть от .env).
    monkeypatch.delenv('LLM_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    parser = AdaptiveBridgeParser(source_name=EXAMPLE_SOURCE_NAME)
    parser._adaptive_parser._orchestrator = _FakeOrchestrator()

    response = await parser.parse(
        EXAMPLE_URL,
        search_task_id=SEARCH_TASK_ID,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    assert response.meta['source'] == EXAMPLE_SOURCE_NAME
    assert response.meta['search_task_id'] == SEARCH_TASK_ID
    assert len(response.items) >= 1
    # Базовый элемент — поисковая страница; её real-новости уходят в
    # отдельные ParsedItem (см. test_bridge_promotes_news), а также
    # остаются в extra['news'] для обратной совместимости.
    assert response.items[0].title == EXAMPLE_SOURCE_NAME


@pytest.mark.asyncio
async def test_bridge_promotes_news(monkeypatch):
    """Каждая новость из extra.news становится отдельным ParsedItem.

    Пункт 12: BP-2 должен обрабатывать каждую статью как самостоятельное
    событие с полным текстом (ex_text в text), а не только листинг.
    """
    monkeypatch.delenv('LLM_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    parser = AdaptiveBridgeParser(source_name=EXAMPLE_SOURCE_NAME)
    parser._adaptive_parser._orchestrator = _FakeOrchestrator()

    response = await parser.parse(
        EXAMPLE_URL,
        search_task_id=SEARCH_TASK_ID,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )

    # Базовый элемент (поисковая страница) помечен и сохраняет extra.news.
    base = response.items[0]
    assert base.extra.get('search_page') is True
    assert isinstance(base.extra.get('news'), list)

    # Новости продвинуты в отдельные ParsedItem.
    news_items = [
        i
        for i in response.items
        if i.extra.get('news_source') == 'adaptive_news'
    ]
    assert news_items, 'новости должны быть продвинуты в ParsedItem'

    news_entry = base.extra['news'][0]
    promoted = news_items[0]
    assert promoted.url == news_entry['ex_url']
    assert promoted.title == news_entry['ex_title']
    assert promoted.text == news_entry['ex_text']
    assert promoted.media_name == EXAMPLE_SOURCE_NAME
    assert promoted.extra.get('search_page_url') == base.url


def test_bridge_metadata():
    """Метаданные моста корректны."""
    parser = AdaptiveBridgeParser(source_name='lenta.ru')
    assert parser.get_source_name() == 'lenta.ru'
    assert parser.get_parser_type() == PARSER_TYPE_ADAPTIVE


@pytest.mark.asyncio
async def test_cache_adapter_roundtrip(tmp_path):
    """Кэш адаптера сохраняет и возвращает состояние."""
    cache = UnifiedCache(redis_client=_FakeRedis(), cache_dir=str(tmp_path))
    adapter = AdapterState(
        source_name=EXAMPLE_SOURCE_NAME,
        selectors={TITLE_FIELD: TITLE_SELECTOR},
        schema_config={TITLE_FIELD: 'string'},
        confidence=ADAPTER_CONFIDENCE,
    )
    await cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)
    loaded = await cache.get_adapter(EXAMPLE_SOURCE_NAME)
    assert loaded is not None
    assert loaded.source_name == EXAMPLE_SOURCE_NAME
    assert loaded.confidence == ADAPTER_CONFIDENCE


@pytest.mark.asyncio
async def test_cache_profile_roundtrip(tmp_path):
    """Кэш профиля сохраняет и возвращает данные."""
    cache = UnifiedCache(cache_dir=str(tmp_path))
    await cache.set_profile(EXAMPLE_SOURCE_NAME, {'cookies': {'a': 'b'}})
    profile = await cache.get_profile(EXAMPLE_SOURCE_NAME)
    assert profile == {'cookies': {'a': 'b'}}


@pytest.mark.asyncio
async def test_article_text_cache_roundtrip(tmp_path):
    """Кэш полного текста статьи сохраняет и возвращает текст и метод."""
    cache = UnifiedCache(cache_dir=str(tmp_path))
    url = 'https://example.com/about/news/1'
    await cache.set_article_text(url, 'Полный текст новости.', 'llm')
    cached = await cache.get_article_text(url)
    assert cached == {'text': 'Полный текст новости.', 'method': 'llm'}

    # Несуществующий URL — None.
    assert await cache.get_article_text('https://example.com/other') is None


@pytest.mark.asyncio
async def test_circuit_breaker_block_and_unblock(tmp_path):
    """Circuit breaker: блокировка/разблокировка и счётчик отказов."""
    cache = UnifiedCache(redis_client=_FakeRedis(), cache_dir=str(tmp_path))

    assert await cache.is_source_blocked(EXAMPLE_SOURCE_NAME) is False
    await cache.block_source(EXAMPLE_SOURCE_NAME, ttl=3600)
    assert await cache.is_source_blocked(EXAMPLE_SOURCE_NAME) is True

    await cache.unblock_source(EXAMPLE_SOURCE_NAME)
    assert await cache.is_source_blocked(EXAMPLE_SOURCE_NAME) is False

    # Счётчик подряд идущих отказов.
    assert await cache.get_fail_count(EXAMPLE_SOURCE_NAME) == 0
    assert await cache.increment_fail_count(EXAMPLE_SOURCE_NAME) == 1
    assert await cache.increment_fail_count(EXAMPLE_SOURCE_NAME) == 2
    assert await cache.get_fail_count(EXAMPLE_SOURCE_NAME) == 2
    await cache.reset_fail_count(EXAMPLE_SOURCE_NAME)
    assert await cache.get_fail_count(EXAMPLE_SOURCE_NAME) == 0


@pytest.mark.asyncio
async def test_hitl_creates_profile(tmp_path, monkeypatch):
    """HITL создаёт профиль при первом обращении."""
    hitl = HITLManager(profiles_dir=str(tmp_path))

    # Имитируем недоступность браузера: _launch_browser возвращает None,
    # что означает "требуется участие человека".
    async def _fake_launch_browser(*args, **kwargs):
        return None

    monkeypatch.setattr(hitl, '_launch_browser', _fake_launch_browser)
    response = await hitl.handle_challenge(EXAMPLE_URL, EXAMPLE_SOURCE_NAME)
    assert response.success is False
    assert response.profile_id is not None


@pytest.mark.asyncio
async def test_hitl_reuses_profile(tmp_path):
    """HITL переиспользует существующий профиль."""
    hitl = HITLManager(profiles_dir=str(tmp_path))
    # Первый вызов создаёт профиль.
    await hitl.handle_challenge(EXAMPLE_URL, EXAMPLE_SOURCE_NAME)
    # Второй вызов находит профиль.
    response = await hitl.handle_challenge(EXAMPLE_URL, EXAMPLE_SOURCE_NAME)
    assert response.success is True
