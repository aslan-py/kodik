"""Тесты для src/bp1/cli.py."""

import pytest

from src.bp1.cli import _clear_task_redis_keys
from src.bp1.models import Competitor, SearchTask, Source


class _FakeRedis:
    """Фейковый Redis-клиент: хранилище в памяти, поддержка delete(*keys)."""

    def __init__(self, initial: dict[str, str] | None = None):
        self._store: dict[str, str] = dict(initial or {})

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted


@pytest.mark.asyncio
async def test_clear_task_redis_keys_deletes_only_existing_tasks(session):
    """Удаляются только ключи задач, реально существующих в БД."""
    competitor = Competitor(name='CLI Test Competitor')
    source = Source(name='cli-test-source.ru')
    session.add_all([competitor, source])
    await session.flush()

    task = SearchTask(
        competitor_id=competitor.id, source_id=source.id, trigger_id=None
    )
    session.add(task)
    await session.flush()

    foreign_key = '999999999'  # числовой ключ постороннего инстанса/системы
    redis = _FakeRedis(
        initial={
            str(task.id): 'somehash',
            foreign_key: 'not-ours',
        }
    )

    task_keys, deleted = await _clear_task_redis_keys(session, redis)

    assert str(task.id) in task_keys
    assert deleted >= 1
    assert await redis.get(str(task.id)) is None
    # Ключ постороннего инстанса/системы не должен быть тронут.
    assert await redis.get(foreign_key) == 'not-ours'


@pytest.mark.asyncio
async def test_clear_task_redis_keys_no_tasks_returns_empty():
    """Без задач (пустой список ID) ничего не удаляется, redis.delete не
    вызывается."""

    class _EmptyResult:
        def all(self):
            return []

    class _FakeSession:
        async def execute(self, stmt):
            return _EmptyResult()

    redis = _FakeRedis(initial={'123': 'x'})

    task_keys, deleted = await _clear_task_redis_keys(_FakeSession(), redis)

    assert task_keys == []
    assert deleted == 0
    # Ключ, не связанный ни с одной задачей, не должен быть тронут.
    assert await redis.get('123') == 'x'
