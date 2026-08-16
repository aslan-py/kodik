"""Интеграция автопокрытия задачами с точками входа BP-1."""

import pytest

from core.pipeline.registry import STAGES
from src.bp1 import pipeline, search_task_coverage


class FakeSessionContext:
    def __init__(self, events: list, session=None):
        self.events = events
        self.session = session or self

    async def __aenter__(self):
        self.events.append(('session_enter', self.session))
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        self.events.append(('session_exit', self.session))

    async def commit(self):
        self.events.append(('commit', self))


class FakeRedisManager:
    def __init__(self, events: list):
        self.events = events
        self.client = object()

    async def get_client(self):
        self.events.append(('redis_get', self.client))
        return self.client

    async def close(self):
        self.events.append(('redis_close', self.client))


@pytest.mark.asyncio
async def test_run_bp1_commits_coverage_before_crawl(monkeypatch):
    events = []
    session_context = FakeSessionContext(events)
    redis_manager = FakeRedisManager(events)

    async def fake_sync(session):
        events.append(('sync', session))
        return 3

    class _FakeOrchestrator:
        def __init__(self):
            self._strategies = {'FAST': object()}

    class _FakeAdaptiveParser:
        def __init__(self):
            self._orchestrator = _FakeOrchestrator()

    class _FakeParser:
        def __init__(self):
            self._adaptive_parser = _FakeAdaptiveParser()

    class FakeRunner:
        def __init__(self, **kwargs):
            events.append(('runner_init', kwargs))
            self._parser = _FakeParser()

        async def run_all(self, session, redis_client):
            events.append(('crawl', session, redis_client))
            return [{'status': 'saved'}, {'status': 'skipped'}]

    monkeypatch.setattr(pipeline, 'AsyncSessionLocal', lambda: session_context)
    monkeypatch.setattr(pipeline, 'redis_client_instance', redis_manager)
    monkeypatch.setattr(pipeline, 'sync_search_task_coverage', fake_sync)
    monkeypatch.setattr(pipeline, 'AdaptiveRunner', FakeRunner)

    result = await pipeline.run_bp1()

    sync_event = next(item for item in events if item[0] == 'sync')
    crawl_event = next(item for item in events if item[0] == 'crawl')
    assert events.index(sync_event) < events.index(crawl_event)
    assert sync_event[1] is crawl_event[1] is session_context
    assert any(
        event[0] == 'commit'
        and events.index(sync_event) < index < events.index(crawl_event)
        for index, event in enumerate(events)
    )
    assert result == {
        'tasks': 2,
        'saved': 1,
        'unchanged': 0,
        'error': 0,
        'skipped': 1,
        'success_rate': 0.5,
        'by_strategy': {},
        'quality_levels': {},
        'low_quality_sources': [],
        'source_items': 0,
        'empty_results': 0,
        'empty_by_reason': {},
        'search_tasks_created': 3,
    }


@pytest.mark.asyncio
async def test_standalone_sync_commits_without_starting_crawl(monkeypatch):
    events = []
    session_context = FakeSessionContext(events)

    async def fake_sync(session):
        events.append(('sync', session))
        return 7

    monkeypatch.setattr(
        search_task_coverage, 'AsyncSessionLocal', lambda: session_context
    )
    monkeypatch.setattr(
        search_task_coverage, 'sync_search_task_coverage', fake_sync
    )

    result = await search_task_coverage.run_search_task_coverage()

    assert result == {'search_tasks_created': 7}
    assert [event[0] for event in events] == [
        'session_enter',
        'sync',
        'commit',
        'session_exit',
    ]


def test_real_bp1_preflight_allows_empty_search_task_table():
    assert STAGES[1].requires is None
