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
    # DEFAULT_MAX_NEWS=1 — собирается первый элемент (сайт-заглушка),
    # реальный заголовок новости уходит в extra['news'].
    assert response.items[0].title == EXAMPLE_SOURCE_NAME


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
