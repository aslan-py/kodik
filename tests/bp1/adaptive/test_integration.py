"""Интеграционные тесты для адаптивного пакета."""

import pytest

from core.config import settings
from src.bp1.adaptive.core.cache import UnifiedCache
from src.bp1.adaptive.integration.bridge import AdaptiveBridgeParser
from src.bp1.adaptive.schemas import (
    AdapterState,
    ProbedUrl,
    StrategyResult,
    StrategyType,
)
from src.bp1.adaptive.strategies.hitl import HITLManager

from .constants import (
    ADAPTER_CONFIDENCE,
    COMPETITOR,
    EXAMPLE_SOURCE_NAME,
    EXAMPLE_URL,
    NEWS_LINK,
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
    monkeypatch.setattr(settings, 'llm_api_key', None)
    parser = AdaptiveBridgeParser(source_name=EXAMPLE_SOURCE_NAME)
    parser._adaptive_parser._orchestrator = _FakeOrchestrator()

    response = await parser.parse(
        EXAMPLE_URL,
        search_task_id=SEARCH_TASK_ID,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    assert response.meta.source == EXAMPLE_SOURCE_NAME
    assert response.meta.items_count == len(response.items)
    assert response.meta.empty_reason is None
    assert response.meta.search_task_id == SEARCH_TASK_ID
    assert len(response.items) >= 1
    # Страница результатов поиска сама не событие БП-1 (её нет в контракте
    # ABOUT.md) — items содержит только продвинутые новости.
    assert response.items[0].url == NEWS_LINK


@pytest.mark.asyncio
async def test_bridge_meta_matches_about_contract(monkeypatch):
    """``meta`` и ``metrics`` разделены по контракту ABOUT.md.

    ``meta`` — только факты о запросе (закрытый список полей,
    ``ParsedMeta``); служебные/диагностические поля (``probed_url``,
    ``strategy_used``, ``quality_status``, ``quality_levels``, ...) обязаны
    жить в ``metrics``, а не просачиваться в ``meta``.
    """
    monkeypatch.setattr(settings, 'llm_api_key', None)
    parser = AdaptiveBridgeParser(source_name=EXAMPLE_SOURCE_NAME)
    parser._adaptive_parser._orchestrator = _FakeOrchestrator()

    response = await parser.parse(
        EXAMPLE_URL,
        search_task_id=SEARCH_TASK_ID,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )

    assert response.meta.model_dump().keys() == {
        'search_task_id',
        'source',
        'competitor',
        'trigger',
        'source_request_url',
        'fetched_at',
        'items_count',
        'empty_reason',
    }
    assert response.metrics.strategy_used == StrategyType.FAST.value
    assert response.metrics.quality_status is not None


@pytest.mark.asyncio
async def test_bridge_zero_results_still_routes_metrics(monkeypatch):
    """Нулевая выдача (news == []) — тоже страница поиска, не событие.

    Регресс-тест на реальный баг (найден на живом прогоне source=lenta.ru,
    search_task_id=621, 0 найденных новостей): код различал «страницу
    поиска» по истинности списка новостей (``if news:``), а не по наличию
    ключа ``news`` в extra. При пустой выдаче условие было ложным, поэтому
    служебная страница поиска не считалась служебной и проваливалась в
    ``items`` как обычное событие — вместе со всей диагностикой
    (``quality_levels``/``relevance_mode``/``news_total``/``file_saved``),
    которая должна была уйти в ``metrics``.
    """
    monkeypatch.setattr(settings, 'llm_api_key', None)
    parser = AdaptiveBridgeParser(source_name=EXAMPLE_SOURCE_NAME)

    class _NoLinksOrchestrator:
        async def fetch_with_degradation(self, url: str, **kwargs):
            html = '<html><body>Ничего не найдено</body></html>'
            return StrategyResult(
                strategy=StrategyType.FAST,
                success=True,
                data=html,
                content_length=len(html),
            )

    parser._adaptive_parser._orchestrator = _NoLinksOrchestrator()

    response = await parser.parse(
        EXAMPLE_URL,
        search_task_id=SEARCH_TASK_ID,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )

    # Ни одной новости не найдено -> служебная страница поиска не событие,
    # items пуст (а не 1 элемент со слипшейся диагностикой в extra).
    assert response.items == []
    assert response.meta.items_count == 0
    assert response.meta.empty_reason == 'no_extractable_items'
    assert response.metrics.news_total == 0
    assert response.metrics.quality_levels is not None
    assert response.meta.model_dump().keys() == {
        'search_task_id',
        'source',
        'competitor',
        'trigger',
        'source_request_url',
        'fetched_at',
        'items_count',
        'empty_reason',
    }


@pytest.mark.asyncio
async def test_bridge_promotes_news(monkeypatch):
    """Каждая новость из страницы результатов поиска — отдельный ParsedItem.

    Пункт 12: BP-2 должен обрабатывать каждую статью как самостоятельное
    событие с полным текстом (title/text), а не только листинг. Страница
    результатов поиска сама в items не попадает (см.
    test_bridge_returns_parsed_response) — раскладывается целиком.
    extra намеренно пуст (по запросу) — вся диагностика извлечения
    (ex_method/relevance/enrichment/...) больше не сериализуется.
    """
    monkeypatch.setattr(settings, 'llm_api_key', None)
    parser = AdaptiveBridgeParser(source_name=EXAMPLE_SOURCE_NAME)
    parser._adaptive_parser._orchestrator = _FakeOrchestrator()

    response = await parser.parse(
        EXAMPLE_URL,
        search_task_id=SEARCH_TASK_ID,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )

    assert response.items, 'новости должны быть продвинуты в ParsedItem'
    promoted = response.items[0]
    assert promoted.url == NEWS_LINK
    assert promoted.media_name == EXAMPLE_SOURCE_NAME
    assert promoted.extra == {}


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
    assert cached == {
        'text': 'Полный текст новости.',
        'method': 'llm',
        'length': len('Полный текст новости.'),
        'complete': True,
        'possibly_incomplete': False,
    }

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
async def test_probed_url_cache_roundtrip(tmp_path):
    """Кэш probed URL сохраняет и возвращает результат пробинга."""
    cache = UnifiedCache(redis_client=_FakeRedis(), cache_dir=str(tmp_path))
    probed = ProbedUrl(
        source_name=EXAMPLE_SOURCE_NAME,
        search_url='https://example.com/search?text=qqq',
        search_method='GET',
        search_params={'text': 'qqq'},
        confidence=1.0,
    )
    await cache.set_probed_url(EXAMPLE_SOURCE_NAME, probed)
    loaded = await cache.get_probed_url(EXAMPLE_SOURCE_NAME)
    assert loaded is not None
    assert loaded.search_url == probed.search_url
    assert loaded.search_method == 'GET'
    assert loaded.search_params == {'text': 'qqq'}
    assert loaded.confidence == 1.0

    await cache.clear_probed_url(EXAMPLE_SOURCE_NAME)
    assert await cache.get_probed_url(EXAMPLE_SOURCE_NAME) is None


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
