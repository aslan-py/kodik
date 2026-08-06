"""Интеграционные тесты для адаптивного пакета."""

import pytest

from src.bp1.adaptive.bridge import AdaptiveBridgeParser
from src.bp1.adaptive.cache import UnifiedCache
from src.bp1.adaptive.hitl import HITLManager
from src.bp1.adaptive.schemas import AdapterState, StrategyResult, StrategyType

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
async def test_bridge_returns_parsed_response():
    """AdaptiveBridgeParser возвращает ParsedResponse."""
    parser = AdaptiveBridgeParser(source_name='example.com')
    parser._adaptive_parser._orchestrator = _FakeOrchestrator()

    response = await parser.parse(
        'https://example.com',
        search_task_id=1,
        competitor='ООО АРХИТЕХ',
        trigger='ИИ',
    )
    assert response.meta['source'] == 'example.com'
    assert response.meta['search_task_id'] == 1
    assert len(response.items) >= 1
    assert response.items[0].title == 'Новость про ИИ'


def test_bridge_metadata():
    """Метаданные моста корректны."""
    parser = AdaptiveBridgeParser(source_name='lenta.ru')
    assert parser.get_source_name() == 'lenta.ru'
    assert parser.get_parser_type() == 'adaptive'


@pytest.mark.asyncio
async def test_cache_adapter_roundtrip(tmp_path):
    """Кэш адаптера сохраняет и возвращает состояние."""
    cache = UnifiedCache(redis_client=_FakeRedis(), cache_dir=str(tmp_path))
    adapter = AdapterState(
        source_name='example.com',
        selectors={'title': 'a'},
        schema_config={'title': 'string'},
        confidence=0.9,
    )
    await cache.set_adapter('example.com', adapter)
    loaded = await cache.get_adapter('example.com')
    assert loaded is not None
    assert loaded.source_name == 'example.com'
    assert loaded.confidence == 0.9


@pytest.mark.asyncio
async def test_cache_profile_roundtrip(tmp_path):
    """Кэш профиля сохраняет и возвращает данные."""
    cache = UnifiedCache(cache_dir=str(tmp_path))
    await cache.set_profile('example.com', {'cookies': {'a': 'b'}})
    profile = await cache.get_profile('example.com')
    assert profile == {'cookies': {'a': 'b'}}


@pytest.mark.asyncio
async def test_hitl_creates_profile(tmp_path):
    """HITL создаёт профиль при первом обращении."""
    hitl = HITLManager(profiles_dir=str(tmp_path))
    response = await hitl.handle_challenge('https://example.com', 'example.com')
    assert response.success is False
    assert response.profile_id is not None


@pytest.mark.asyncio
async def test_hitl_reuses_profile(tmp_path):
    """HITL переиспользует существующий профиль."""
    hitl = HITLManager(profiles_dir=str(tmp_path))
    # Первый вызов создаёт профиль.
    await hitl.handle_challenge('https://example.com', 'example.com')
    # Второй вызов находит профиль.
    response = await hitl.handle_challenge('https://example.com', 'example.com')
    assert response.success is True
