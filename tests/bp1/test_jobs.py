"""Тесты заданий сбора BP-1 (``src/bp1/jobs.py``).

Проверяют контракт, на который опирается планировщик задач:

- источники/конкуренты/связки создаются идемпотентно («найти или создать»);
- матрица пар строится верно для каждого из трёх режимов сбора;
- результат JSON-сериализуем и не содержит Pydantic-моделей/датавремени;
- отсутствующий источник не приводит к побочным эффектам.

БД и Redis не используются: сессия и подключение подменяются фейками,
поэтому тесты идут без внешних сервисов.
"""

from __future__ import annotations

import json

import pytest

from src.bp1 import jobs


class _FakeRedis:
    """Заглушка Redis-клиента."""

    async def get(self, key):
        return None

    async def set(self, key, value, ex=None):
        return None

    async def delete(self, *keys):
        return 0


class _FakeRedisInstance:
    """Заглушка синглтона RedisClient (get_client/close)."""

    def __init__(self):
        self.closed = 0

    async def get_client(self):
        return _FakeRedis()

    async def close(self):
        self.closed += 1


class _Row:
    """Строка БД с произвольными полями."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Result:
    """Результат session.execute с интерфейсом scalars()/all()."""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Сессия БД: отдаёт заранее заданные ответы на запросы по очереди."""

    def __init__(self, responses: list[list]):
        self._responses = list(responses)
        self.added: list = []
        self.commits = 0
        self._next_id = 1000

    async def execute(self, stmt):
        rows = self._responses.pop(0) if self._responses else []
        return _Result(rows)

    def add(self, obj):
        self._next_id += 1
        obj.id = self._next_id
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _patch_env(monkeypatch, session: _FakeSession) -> _FakeRedisInstance:
    """Подменяет фабрику сессий и Redis в модуле заданий."""
    redis_instance = _FakeRedisInstance()
    monkeypatch.setattr(jobs, 'AsyncSessionLocal', lambda: session)
    monkeypatch.setattr(jobs, 'redis_client_instance', redis_instance)
    return redis_instance


def _patch_runner(monkeypatch, results: list[dict]) -> dict:
    """Подменяет AdaptiveRunner: фиксирует, какие задачи были запущены."""
    captured: dict = {}

    class _FakeRunner:
        async def run_all(self, session, redis_client, task_ids=None):
            captured['task_ids'] = task_ids
            return results

    monkeypatch.setattr(jobs, '_make_runner', lambda *a, **kw: _FakeRunner())
    return captured


# ============================================================================
# _ensure_search_tasks — идемпотентность матрицы
# ============================================================================


@pytest.mark.asyncio
async def test_ensure_search_tasks_creates_missing_pairs():
    """Недостающие связки создаются, существующие переиспользуются."""
    existing = _Row(id=1, source_id=10, competitor_id=100)
    session = _FakeSession([[existing]])

    task_ids = await jobs._ensure_search_tasks(session, [10], [100, 200])

    # Первая пара найдена, вторая создана.
    assert len(task_ids) == 2
    assert task_ids[0] == 1
    assert len(session.added) == 1
    assert session.added[0].source_id == 10
    assert session.added[0].competitor_id == 200
    # Новые связки без триггера — под частичный уникальный индекс БД.
    assert session.added[0].trigger_id is None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ensure_search_tasks_idempotent_when_all_exist():
    """Если все пары уже есть — ничего не создаётся и не коммитится."""
    existing = [
        _Row(id=1, source_id=10, competitor_id=100),
        _Row(id=2, source_id=10, competitor_id=200),
    ]
    session = _FakeSession([existing])

    task_ids = await jobs._ensure_search_tasks(session, [10], [100, 200])

    assert sorted(task_ids) == [1, 2]
    assert session.added == []
    assert session.commits == 0


@pytest.mark.asyncio
async def test_ensure_search_tasks_empty_input():
    """Пустой источник или конкурент — пустая матрица без запросов."""
    session = _FakeSession([])
    assert await jobs._ensure_search_tasks(session, [], [1]) == []
    assert await jobs._ensure_search_tasks(session, [1], []) == []


# ============================================================================
# collect_source
# ============================================================================


@pytest.mark.asyncio
async def test_collect_source_missing_source_has_no_side_effects(monkeypatch):
    """Неизвестный источник: ничего не создаётся, статус говорит причину."""
    # 1) поиск по имени -> пусто, 2) перебор всех источников -> пусто
    session = _FakeSession([[], []])
    redis_instance = _patch_env(monkeypatch, session)

    result = await jobs.collect_source('unknown.example')

    assert result['status'] == 'source_not_found'
    assert result['tasks'] == 0
    assert session.added == []
    # Redis-соединение закрыто даже на раннем выходе.
    assert redis_instance.closed == 1


@pytest.mark.asyncio
async def test_collect_source_runs_all_competitors(monkeypatch):
    """Источник найден: матрица строится по всем активным конкурентам."""
    source = _Row(id=10, name='https://lenta.ru/', is_active=True)
    session = _FakeSession(
        [
            [source],  # _find_source: точное совпадение
            [100, 200],  # _active_competitor_ids
            [],  # _ensure_search_tasks: существующих связок нет
        ]
    )
    _patch_env(monkeypatch, session)
    captured = _patch_runner(
        monkeypatch,
        [
            {'status': 'saved', 'strategy': 'FAST'},
            {'status': 'unchanged', 'strategy': 'BROWSER'},
        ],
    )

    result = await jobs.collect_source('lenta.ru')

    assert result['status'] == 'ok'
    assert result['source'] == 'https://lenta.ru/'
    assert result['competitors'] == 2
    # Запущены ровно созданные связки.
    assert len(captured['task_ids']) == 2
    # Сводка посчитана.
    assert result['tasks'] == 2
    assert result['success_rate'] == 1.0
    assert result['by_strategy'] == {'FAST': 1, 'BROWSER': 1}


@pytest.mark.asyncio
async def test_collect_source_inactive_source(monkeypatch):
    """Выключенный источник не собирается."""
    source = _Row(id=10, name='https://lenta.ru/', is_active=False)
    session = _FakeSession([[source]])
    _patch_env(monkeypatch, session)

    result = await jobs.collect_source('lenta.ru')

    assert result['status'] == 'source_inactive'
    assert result['tasks'] == 0


# ============================================================================
# collect_competitor
# ============================================================================


@pytest.mark.asyncio
async def test_collect_competitor_creates_missing_competitor(monkeypatch):
    """Конкурента, которого нет в БД, задание создаёт само."""
    session = _FakeSession(
        [
            [],  # поиск конкурента -> не найден
            [10, 20],  # _active_source_ids
            [],  # _ensure_search_tasks
        ]
    )
    _patch_env(monkeypatch, session)
    _patch_runner(monkeypatch, [{'status': 'saved', 'strategy': 'FAST'}])

    result = await jobs.collect_competitor('Сбербанк', inn='7707083893')

    assert result['status'] == 'ok'
    assert result['competitor_created'] is True
    assert result['sources'] == 2
    # Конкурент создан с переданным ИНН — иначе гос. источники пропустят
    # задачу с 'not INN'.
    created = session.added[0]
    assert created.name == 'Сбербанк'
    assert created.inn == '7707083893'


@pytest.mark.asyncio
async def test_collect_competitor_reuses_existing(monkeypatch):
    """Существующий конкурент переиспользуется, дубль не создаётся."""
    competitor = _Row(id=100, name='Сбербанк', inn='7707083893', is_active=True)
    session = _FakeSession([[competitor], [10], []])
    _patch_env(monkeypatch, session)
    _patch_runner(monkeypatch, [{'status': 'saved'}])

    result = await jobs.collect_competitor('Сбербанк')

    assert result['competitor_created'] is False
    assert result['competitor_id'] == 100
    # Дубль конкурента не создан (связки SearchTask при этом создаются —
    # это ожидаемо, матрица достраивается).
    from src.bp1.models import Competitor

    assert [o for o in session.added if isinstance(o, Competitor)] == []


@pytest.mark.asyncio
async def test_collect_competitor_backfills_inn(monkeypatch):
    """ИНН проставляется существующему конкуренту, если его не было."""
    competitor = _Row(id=100, name='Сбербанк', inn=None, is_active=True)
    session = _FakeSession([[competitor], [10], []])
    _patch_env(monkeypatch, session)
    _patch_runner(monkeypatch, [{'status': 'saved'}])

    await jobs.collect_competitor('Сбербанк', inn='7707083893')

    assert competitor.inn == '7707083893'


@pytest.mark.asyncio
async def test_collect_competitor_empty_name(monkeypatch):
    """Пустое название не создаёт мусорную запись в БД."""
    session = _FakeSession([])
    _patch_env(monkeypatch, session)

    result = await jobs.collect_competitor('   ')

    assert result['status'] == 'empty_competitor'
    assert session.added == []


# ============================================================================
# collect_source_competitor
# ============================================================================


def _patch_pair_runner(monkeypatch, result: dict) -> dict:
    """Подменяет AdaptiveRunner.run_source_competitor: фиксирует аргументы
    вызова вместо реального прогона."""
    captured: dict = {}

    class _FakeRunner:
        async def run_source_competitor(
            self, source, competitor, session, redis_client
        ):
            captured['source'] = source
            captured['competitor'] = competitor
            return dict(result)

    monkeypatch.setattr(jobs, '_make_runner', lambda *a, **kw: _FakeRunner())
    return captured


@pytest.mark.asyncio
async def test_collect_source_competitor_creates_missing_competitor(
    monkeypatch,
):
    """Конкурента, которого нет в БД, задание создаёт само (с ИНН)."""
    session = _FakeSession([[]])  # поиск конкурента -> не найден
    _patch_env(monkeypatch, session)
    captured = _patch_pair_runner(monkeypatch, {'status': 'ok'})

    result = await jobs.collect_source_competitor(
        'lenta.ru', 'Сбербанк', inn='7707083893'
    )

    assert result['job'] == 'collect_source_competitor'
    assert result['status'] == 'ok'
    created = session.added[0]
    assert created.name == 'Сбербанк'
    assert created.inn == '7707083893'
    # Раннер вызван ровно для этой пары, не для всей матрицы.
    assert captured['source'] == 'lenta.ru'
    assert captured['competitor'] == 'Сбербанк'


@pytest.mark.asyncio
async def test_collect_source_competitor_backfills_inn(monkeypatch):
    """ИНН проставляется существующему конкуренту, если его не было."""
    competitor = _Row(id=100, name='Сбербанк', inn=None, is_active=True)
    session = _FakeSession([[competitor]])
    _patch_env(monkeypatch, session)
    _patch_pair_runner(monkeypatch, {'status': 'ok'})

    await jobs.collect_source_competitor(
        'lenta.ru', 'Сбербанк', inn='7707083893'
    )

    assert competitor.inn == '7707083893'
    from src.bp1.models import Competitor

    # Дубль не создан — переиспользован существующий.
    assert [o for o in session.added if isinstance(o, Competitor)] == []


@pytest.mark.asyncio
async def test_collect_source_competitor_reuses_existing_with_inn(
    monkeypatch,
):
    """Конкурент с уже проставленным ИНН не трогается лишний раз."""
    competitor = _Row(id=100, name='Сбербанк', inn='7707083893', is_active=True)
    session = _FakeSession([[competitor]])
    _patch_env(monkeypatch, session)
    _patch_pair_runner(monkeypatch, {'status': 'ok'})

    result = await jobs.collect_source_competitor('lenta.ru', 'Сбербанк')

    assert result['status'] == 'ok'
    assert session.commits == 0


@pytest.mark.asyncio
async def test_collect_source_competitor_empty_name(monkeypatch):
    """Пустое название не создаёт мусорную запись и не запускает раннер."""
    session = _FakeSession([])
    _patch_env(monkeypatch, session)

    result = await jobs.collect_source_competitor('lenta.ru', '   ')

    assert result['status'] == 'empty_competitor'
    assert session.added == []


@pytest.mark.asyncio
async def test_collect_source_competitor_result_is_json_serializable(
    monkeypatch,
):
    """Результат задания сериализуется в JSON — тот же контракт очереди."""
    competitor = _Row(id=100, name='Сбербанк', inn='7707083893', is_active=True)
    session = _FakeSession([[competitor]])
    _patch_env(monkeypatch, session)
    _patch_pair_runner(
        monkeypatch,
        {'status': 'ok', 'strategy': 'FEED', 'source_items': 1},
    )

    result = await jobs.collect_source_competitor('lenta.ru', 'Сбербанк')

    encoded = json.dumps(result, ensure_ascii=False)
    assert json.loads(encoded)['job'] == 'collect_source_competitor'


# ============================================================================
# collect_all
# ============================================================================


@pytest.mark.asyncio
async def test_collect_all_builds_full_matrix(monkeypatch):
    """ensure_matrix=True достраивает все пары источник x конкурент."""
    session = _FakeSession(
        [
            [10, 20],  # источники
            [100, 200],  # конкуренты
            [],  # существующих связок нет
        ]
    )
    _patch_env(monkeypatch, session)
    captured = _patch_runner(monkeypatch, [{'status': 'saved'}] * 4)

    result = await jobs.collect_all()

    # 2 источника x 2 конкурента = 4 связки.
    assert len(session.added) == 4
    assert len(captured['task_ids']) == 4
    assert result['sources'] == 2
    assert result['competitors'] == 2


@pytest.mark.asyncio
async def test_collect_all_without_ensure_matrix_creates_nothing(monkeypatch):
    """ensure_matrix=False не пишет в БД — только уже заведённые связки."""
    session = _FakeSession(
        [
            [10, 20],  # источники
            [100, 200],  # конкуренты
            [1, 2],  # id активных связок
        ]
    )
    _patch_env(monkeypatch, session)
    captured = _patch_runner(monkeypatch, [{'status': 'saved'}] * 2)

    await jobs.collect_all(ensure_matrix=False)

    assert session.added == []
    assert captured['task_ids'] == [1, 2]


@pytest.mark.asyncio
async def test_collect_all_empty_db(monkeypatch):
    """Пустая БД: задание отрабатывает без ошибок и без запуска сбора."""
    session = _FakeSession([[], []])
    _patch_env(monkeypatch, session)

    result = await jobs.collect_all()

    assert result['tasks'] == 0
    assert result['success_rate'] == 0.0


# ============================================================================
# Контракт результата (для очереди задач)
# ============================================================================


@pytest.mark.asyncio
async def test_result_is_json_serializable(monkeypatch):
    """Результат задания сериализуется в JSON без кастомных энкодеров."""
    source = _Row(id=10, name='https://lenta.ru/', is_active=True)
    session = _FakeSession([[source], [100], []])
    _patch_env(monkeypatch, session)
    _patch_runner(
        monkeypatch,
        [
            {
                'status': 'saved',
                'strategy': 'FAST',
                'quality_status': 'ok',
                'quality_levels': {'SCHEMA': {'passed': True}},
                'source': 'https://lenta.ru/',
            }
        ],
    )

    result = await jobs.collect_source('lenta.ru')

    # Именно это делает брокер очереди с возвращаемым значением.
    encoded = json.dumps(result, ensure_ascii=False)
    assert json.loads(encoded)['job'] == 'collect_source'


@pytest.mark.asyncio
async def test_redis_closed_even_on_failure(monkeypatch):
    """Соединение Redis закрывается, даже если задание упало."""
    session = _FakeSession([[_Row(id=10, name='x', is_active=True)], [100], []])
    redis_instance = _patch_env(monkeypatch, session)

    def _boom(*args, **kwargs):
        raise RuntimeError('runner is down')

    monkeypatch.setattr(jobs, '_make_runner', _boom)

    with pytest.raises(RuntimeError, match='runner is down'):
        await jobs.collect_source('lenta.ru')

    assert redis_instance.closed == 1
