"""Тесты конкурентного выполнения задач в ``AdaptiveRunner.run_all``.

Шаг 17 плана рефакторинга (kodik/src/bp1/REFACTORING_PLAN.md, T1):
``max_concurrent`` хранился в конфиге, но ``run_all`` выполнял задачи
строго последовательно. Проверяется:

- параллельно выполняется не больше ``max_concurrent`` задач;
- порядок результатов соответствует порядку задач;
- каждая параллельная задача получает СВОЮ сессию БД (``AsyncSession``
  нельзя использовать одновременно из нескольких корутин);
- неактивные source/competitor по-прежнему пропускаются без запуска;
- ``max_concurrent=1`` сохраняет прежнее поведение (переданная сессия,
  без создания новых);
- исключение из задачи поднимается наружу, но только после завершения
  всех параллельных задач (без висящих корутин).
"""

from __future__ import annotations

import asyncio

import pytest

from src.bp1.adaptive.integration.runner import AdaptiveRunner


class _FakeSession:
    """Заглушка AsyncSession: отдаёт заранее заданный список задач."""

    def __init__(self, tasks: list | None = None):
        self._tasks = tasks or []
        self.closed = False

    async def execute(self, stmt):
        tasks = self._tasks

        class _Result:
            @staticmethod
            def scalars():
                class _Scalars:
                    @staticmethod
                    def all():
                        return tasks

                return _Scalars()

        return _Result()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True
        return False


class _FakeFlag:
    """Объект с полем is_active (Source/Competitor)."""

    def __init__(self, is_active: bool = True):
        self.is_active = is_active


class _FakeTask:
    """Заглушка SearchTask."""

    def __init__(
        self,
        task_id: int,
        source_active: bool = True,
        competitor_active: bool = True,
    ):
        self.id = task_id
        self.source = _FakeFlag(source_active)
        self.competitor = _FakeFlag(competitor_active)


async def _noop_check_health() -> bool:
    return True


def _make_runner(max_concurrent: int, tasks: list) -> AdaptiveRunner:
    """Runner с подменённой фабрикой сессий (живая БД не нужна)."""
    runner = AdaptiveRunner(max_concurrent=max_concurrent)
    created_sessions: list[_FakeSession] = []

    def _factory():
        session = _FakeSession(tasks)
        created_sessions.append(session)
        return session

    runner._session_factory = _factory
    runner.created_sessions = created_sessions  # для проверок в тестах
    # run_all теперь дёргает check_health() в начале прогона — без мока
    # это реальный сетевой вызов к провайдеру прокси (settings.sx_org_
    # api_key может быть задан в .env), не нужный этим тестам конкурентности.
    runner._proxy_pool.check_health = _noop_check_health
    return runner


@pytest.mark.asyncio
async def test_run_all_respects_max_concurrent():
    """Одновременно выполняется не более max_concurrent задач."""
    tasks = [_FakeTask(i) for i in range(1, 11)]
    runner = _make_runner(max_concurrent=3, tasks=tasks)

    active = 0
    peak = 0

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {'status': 'ok', 'search_task_id': task_id}

    runner.run_task = _fake_run_task

    results = await runner.run_all(_FakeSession(tasks), redis_client=None)

    assert len(results) == 10
    assert peak <= 3
    # Параллелизм реально был (иначе peak был бы 1).
    assert peak > 1


@pytest.mark.asyncio
async def test_run_all_preserves_result_order():
    """Порядок результатов соответствует порядку задач, несмотря на
    разное время выполнения."""
    tasks = [_FakeTask(i) for i in range(1, 6)]
    runner = _make_runner(max_concurrent=5, tasks=tasks)

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        # Обратная зависимость: ранние задачи завершаются позже.
        await asyncio.sleep(0.01 * (6 - task_id))
        return {'status': 'ok', 'search_task_id': task_id}

    runner.run_task = _fake_run_task

    results = await runner.run_all(_FakeSession(tasks), redis_client=None)

    assert [r['search_task_id'] for r in results] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_run_all_uses_separate_session_per_task():
    """Каждая параллельная задача получает свою сессию, не переданную в
    run_all (AsyncSession не поддерживает конкурентное использование)."""
    tasks = [_FakeTask(i) for i in range(1, 4)]
    runner = _make_runner(max_concurrent=3, tasks=tasks)
    outer_session = _FakeSession(tasks)

    seen_sessions: list[object] = []

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        seen_sessions.append(session)
        return {'status': 'ok', 'search_task_id': task_id}

    runner.run_task = _fake_run_task

    await runner.run_all(outer_session, redis_client=None)

    assert len(seen_sessions) == 3
    # Ни одна задача не получила внешнюю сессию.
    assert outer_session not in seen_sessions
    # Все сессии различны и созданы фабрикой.
    assert len({id(s) for s in seen_sessions}) == 3
    assert len(runner.created_sessions) == 3
    # Сессии закрыты (async with отработал).
    assert all(s.closed for s in runner.created_sessions)


@pytest.mark.asyncio
async def test_run_all_sequential_mode_uses_passed_session():
    """max_concurrent=1 — прежнее поведение: используется переданная
    сессия, новые не создаются."""
    tasks = [_FakeTask(i) for i in range(1, 4)]
    runner = _make_runner(max_concurrent=1, tasks=tasks)
    outer_session = _FakeSession(tasks)

    seen_sessions: list[object] = []

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        seen_sessions.append(session)
        return {'status': 'ok', 'search_task_id': task_id}

    runner.run_task = _fake_run_task

    results = await runner.run_all(outer_session, redis_client=None)

    assert len(results) == 3
    assert all(s is outer_session for s in seen_sessions)
    assert runner.created_sessions == []


@pytest.mark.asyncio
async def test_run_all_skips_inactive_without_running():
    """Неактивные source/competitor пропускаются, run_task не вызывается,
    порядок результатов сохраняется."""
    tasks = [
        _FakeTask(1),
        _FakeTask(2, source_active=False),
        _FakeTask(3, competitor_active=False),
        _FakeTask(4),
    ]
    runner = _make_runner(max_concurrent=3, tasks=tasks)

    ran: list[int] = []

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        ran.append(task_id)
        return {'status': 'ok', 'search_task_id': task_id}

    runner.run_task = _fake_run_task

    results = await runner.run_all(_FakeSession(tasks), redis_client=None)

    assert [r['search_task_id'] for r in results] == [1, 2, 3, 4]
    assert results[1]['status'] == 'skipped'
    assert results[1]['reason'] == 'source_inactive'
    assert results[2]['status'] == 'skipped'
    assert results[2]['reason'] == 'competitor_inactive'
    assert sorted(ran) == [1, 4]


@pytest.mark.asyncio
async def test_run_all_checks_proxy_health_once_before_dispatch():
    """check_health() вызывается ровно один раз за run_all, до запуска
    задач (не на каждую задачу)."""
    tasks = [_FakeTask(i) for i in range(1, 4)]
    runner = _make_runner(max_concurrent=3, tasks=tasks)

    call_order: list[str] = []

    async def _tracked_check_health() -> bool:
        call_order.append('check_health')
        return True

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        call_order.append(f'task:{task_id}')
        return {'status': 'ok', 'search_task_id': task_id}

    runner._proxy_pool.check_health = _tracked_check_health
    runner.run_task = _fake_run_task

    await runner.run_all(_FakeSession(tasks), redis_client=None)

    assert call_order[0] == 'check_health'
    assert call_order.count('check_health') == 1


@pytest.mark.asyncio
async def test_run_all_continues_when_proxy_unavailable():
    """check_health(), сигнализирующий о недоступности прокси (False), не
    прерывает прогон — задачи всё равно выполняются."""
    tasks = [_FakeTask(i) for i in range(1, 4)]
    runner = _make_runner(max_concurrent=3, tasks=tasks)

    async def _unhealthy() -> bool:
        return False

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        return {'status': 'ok', 'search_task_id': task_id}

    runner._proxy_pool.check_health = _unhealthy
    runner.run_task = _fake_run_task

    results = await runner.run_all(_FakeSession(tasks), redis_client=None)

    assert [r['search_task_id'] for r in results] == [1, 2, 3]


@pytest.mark.asyncio
async def test_run_all_propagates_exception_after_all_finish():
    """Исключение из задачи поднимается наружу, но остальные задачи
    успевают завершиться (не остаётся висящих корутин)."""
    tasks = [_FakeTask(i) for i in range(1, 4)]
    runner = _make_runner(max_concurrent=3, tasks=tasks)

    finished: list[int] = []

    async def _fake_run_task(task_id, session, redis_client, **kwargs):
        if task_id == 1:
            raise RuntimeError('task 1 failed')
        await asyncio.sleep(0.01)
        finished.append(task_id)
        return {'status': 'ok', 'search_task_id': task_id}

    runner.run_task = _fake_run_task

    with pytest.raises(RuntimeError, match='task 1 failed'):
        await runner.run_all(_FakeSession(tasks), redis_client=None)

    # Задачи 2 и 3 не были брошены на полпути.
    assert sorted(finished) == [2, 3]
