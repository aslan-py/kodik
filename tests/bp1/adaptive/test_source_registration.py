"""Тесты регистрации источников (SourceRegistrationService)."""

import pytest
from sqlalchemy import select

from src.bp1.adaptive.integration.sources import (
    SourceRegistrationService,
    build_search_url,
    extract_host,
    normalize_source_url,
)
from src.bp1.adaptive.schemas import SourceType
from src.bp1.models import Source

from .constants import (
    REDIS_CLASSIFICATION_KEY,
    SEARCH_QUERY,
    SEARCH_URL,
    SRC_API_HH,
    SRC_API_HH_HOST,
    SRC_EMPTY,
    SRC_FEDRESURS_HOST,
    SRC_FEDRESURS_PORT,
    SRC_INVALID_REF,
    SRC_LENTA_HOST,
    SRC_LENTA_NEWS,
    SRC_LENTA_NORMALIZED,
    SRC_LENTA_UPPER,
    SRC_LENTA_WWW,
    SRC_WHITESPACE,
)


class _FakeRedis:
    """Фейковый Redis-клиент для тестов (in-memory)."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)


# ============================================================================
# extract_host / normalize_source_url / build_search_url
# ============================================================================


@pytest.mark.parametrize(
    ('url', 'expected'),
    [
        (SRC_LENTA_WWW, SRC_LENTA_HOST),
        (SRC_API_HH, SRC_API_HH_HOST),
        (SRC_FEDRESURS_PORT, SRC_FEDRESURS_HOST),
        (SRC_LENTA_UPPER, SRC_LENTA_HOST),
        (SRC_LENTA_HOST, SRC_LENTA_HOST),
    ],
)
def test_extract_host_variants(url, expected):
    assert extract_host(url) == expected


@pytest.mark.parametrize('bad', [SRC_INVALID_REF, SRC_EMPTY, SRC_WHITESPACE])
def test_extract_host_invalid(bad):
    with pytest.raises(ValueError):
        extract_host(bad)


def test_normalize_source_url():
    assert normalize_source_url(SRC_LENTA_WWW) == SRC_LENTA_NORMALIZED


@pytest.mark.parametrize(
    ('source_name', 'expected'),
    [
        (SRC_LENTA_NORMALIZED, SEARCH_URL),
        (SRC_LENTA_HOST, SEARCH_URL),
        (SRC_LENTA_NEWS, SEARCH_URL),
    ],
)
def test_build_search_url(source_name, expected):
    assert build_search_url(source_name, SEARCH_QUERY) == expected


# ============================================================================
# SourceRegistrationService.register
# ============================================================================


@pytest.mark.asyncio
async def test_register_creates_source(session):
    """Регистрация создаёт Source и кэширует классификацию в Redis."""
    fake_redis = _FakeRedis()
    service = SourceRegistrationService(session, redis_client=fake_redis)

    result = await service.register(SRC_LENTA_NEWS, fake_redis)

    assert result.created is True
    assert result.source_name == SRC_LENTA_NORMALIZED
    assert result.host == SRC_LENTA_HOST
    assert result.classification.source_type == SourceType.NEWS

    # В БД появилась запись Source.
    source = (
        await session.execute(
            select(Source).where(Source.name == SRC_LENTA_NORMALIZED)
        )
    ).scalar_one_or_none()
    assert source is not None
    assert source.id == result.source_id

    # В Redis появился ключ классификации.
    assert fake_redis._store.get(REDIS_CLASSIFICATION_KEY) is not None


@pytest.mark.asyncio
async def test_register_is_idempotent(session):
    """Повторная регистрация не создаёт дубль, возвращает created=False."""
    fake_redis = _FakeRedis()
    service = SourceRegistrationService(session, redis_client=fake_redis)

    first = await service.register(SRC_LENTA_NORMALIZED, fake_redis)
    second = await service.register(SRC_LENTA_NEWS, fake_redis)

    assert first.created is True
    assert second.created is False
    assert second.source_id == first.source_id

    count = (
        await session.execute(
            select(Source).where(Source.name == SRC_LENTA_NORMALIZED)
        )
    ).scalar_one_or_none()
    assert count is not None
