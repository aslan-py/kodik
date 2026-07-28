"""Общие фикстуры: движок БД и сессия с откатом после каждого теста."""

import pytest
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.config import settings


@pytest.fixture
async def engine():
    # NullPool + function scope: каждый тест получает свежий engine.
    # Предотвращает конфликты транзакций asyncpg между тестами.
    e = create_async_engine(settings.database_url, poolclass=NullPool)
    yield e
    await e.dispose()


@pytest.fixture
async def session(engine):
    """Сессия без коммита — данные откатываются после каждого теста."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()
