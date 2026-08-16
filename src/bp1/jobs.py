"""Задания сбора BP-1 — публичный API этапа.

Четыре задания, которыми оперирует эксплуатация:

1. :func:`collect_source` — собрать один источник по всем активным
   конкурентам (например, «пройти lenta.ru по всем, кого мониторим»).
2. :func:`collect_competitor` — собрать одного конкурента по всем активным
   источникам; если конкурента ещё нет в БД, он создаётся.
3. :func:`collect_all` — полный прогон: все активные источники × все
   активные конкуренты.
4. :func:`register_source` — поставить новый источник на учёт:
   нормализовать ссылку, категоризировать сайт, записать ``Source`` в БД,
   положить классификацию в кэш и проверить поисковый эндпоинт.

Слои модуля и его соседей
-------------------------
``jobs.py`` (этот модуль) — оркестрация НАБОРОВ: находит/создаёт связки
``SearchTask`` и запускает их через ``AdaptiveRunner``.
``tasks.py`` — уровень ниже: разбор ОДНОЙ ``SearchTask`` классическим
контуром (``run_parser_async``); модуль трогать не нужно, у него свои
потребители (``runner.py``, ``celery_tasks.py``).
``pipeline.py`` — точка входа этапа 1 в общем конвейере (``run_bp1``).

Контракт для постановки в очередь
---------------------------------
Задания намеренно написаны так, чтобы обёртка планировщика (Celery beat /
task) не требовала адаптеров:

- **только примитивы на входе** (``str``/``int``/``bool``/``None``) —
  аргументы переживают сериализацию брокером; сессии, Redis-клиенты и
  ORM-модели наружу не выносятся;
- **самодостаточность** — задание само открывает сессию БД и Redis и само
  их закрывает в ``finally``; вызывающему не нужно готовить контекст;
- **JSON-сериализуемый результат** — обычный ``dict`` без Pydantic-моделей
  и ``datetime``, пригоден как возвращаемое значение задачи;
- **идемпотентность** — источники, конкуренты и связки ``SearchTask``
  создаются по принципу «найти или создать», поэтому повторный запуск
  (в том числе после ретрая) не плодит дубли;
- **async** — в синхронном исполнителе оборачивается ``asyncio.run(...)``.

Пример обёртки (пишется на стороне планировщика, здесь не объявляется)::

    @app.task(bind=True, autoretry_for=(Exception,))
    def collect_all_task(self) -> dict:
        return asyncio.run(collect_all())
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.redis_client import redis_client as redis_client_instance
from src.bp1.models import Competitor, SearchTask, Source
from src.bp1.pipeline import summarize_results

logger = logging.getLogger(__name__)

__all__ = [
    'collect_all',
    'collect_competitor',
    'collect_source',
    'register_source',
]


# ============================================================================
# ВНУТРЕННИЕ ПОМОЩНИКИ
# ============================================================================


def _make_runner(
    headless: bool,
    timeout: int | None,
    max_concurrent: int | None,
):
    """Собирает ``AdaptiveRunner`` с настройками прогона.

    Импорт отложенный: ``adaptive.integration.runner`` тянет за собой
    ``src.bp1.tasks``, и импорт на уровне модуля дал бы цикл при обратной
    ссылке. Заодно не платим за тяжёлые зависимости адаптивного контура
    при простом ``import src.bp1.jobs``.
    """
    from core.config import settings
    from src.bp1.adaptive.integration.runner import AdaptiveRunner

    return AdaptiveRunner(
        mode=settings.bp1_adaptive_mode,
        headless=headless,
        timeout=timeout or settings.bp1_parse_timeout_ms,
        max_concurrent=max_concurrent or settings.bp1_max_concurrent_tasks,
    )


async def _active_source_ids(session: AsyncSession) -> list[int]:
    """ID всех активных источников."""
    stmt = select(Source.id).where(Source.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def _active_competitor_ids(session: AsyncSession) -> list[int]:
    """ID всех активных конкурентов."""
    stmt = select(Competitor.id).where(Competitor.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def _find_source(session: AsyncSession, source: str) -> Source | None:
    """Ищет источник по имени в любой форме записи.

    ``Source.name`` хранится нормализованным (``https://lenta.ru/``), но
    пользователь и планировщик передают источник как угодно: ``lenta.ru``,
    ``https://lenta.ru``, ``https://www.lenta.ru/news``. Сначала пробуем
    точное совпадение нормализованного имени, затем — совпадение по
    hostname среди уже сохранённых источников.
    """
    from src.bp1.adaptive.hostname import try_extract_host
    from src.bp1.adaptive.integration.sources import normalize_source_url

    try:
        normalized = normalize_source_url(source)
    except ValueError:
        return None

    stmt = select(Source).where(Source.name == normalized)
    found = (await session.execute(stmt)).scalar_one_or_none()
    if found is not None:
        return found

    host = try_extract_host(source)
    if host is None:
        return None
    for candidate in (await session.execute(select(Source))).scalars().all():
        if try_extract_host(candidate.name) == host:
            return candidate
    return None


async def _ensure_search_tasks(
    session: AsyncSession,
    source_ids: list[int],
    competitor_ids: list[int],
) -> list[int]:
    """Находит или создаёт связки ``SearchTask`` для матрицы пар.

    Создаются связки без триггера (``trigger_id IS NULL``) — «парсим
    источник в лоб по названию конкурента»; на такие пары в БД есть
    частичный уникальный индекс, поэтому повторный вызов дублей не даёт.

    Returns:
        ID всех связок матрицы (и найденных, и созданных).
    """
    if not source_ids or not competitor_ids:
        return []

    existing_stmt = select(SearchTask).where(
        SearchTask.source_id.in_(source_ids),
        SearchTask.competitor_id.in_(competitor_ids),
        SearchTask.trigger_id.is_(None),
    )
    existing = (await session.execute(existing_stmt)).scalars().all()
    by_pair = {(t.source_id, t.competitor_id): t for t in existing}

    task_ids: list[int] = []
    created = 0
    for source_id in source_ids:
        for competitor_id in competitor_ids:
            task = by_pair.get((source_id, competitor_id))
            if task is None:
                task = SearchTask(
                    source_id=source_id,
                    competitor_id=competitor_id,
                    trigger_id=None,
                    is_active=True,
                )
                session.add(task)
                await session.flush()
                created += 1
            task_ids.append(task.id)

    if created:
        await session.commit()
        logger.info('Создано новых связок источник-конкурент: %d', created)
    return task_ids


async def _run_and_summarize(
    *,
    job: str,
    task_ids: list[int],
    headless: bool,
    timeout: int | None,
    max_concurrent: int | None,
    session: AsyncSession,
    redis_client: Any,
    **extra: Any,
) -> dict[str, Any]:
    """Запускает связки и сворачивает результат в сводку прогона."""
    if not task_ids:
        return {
            'job': job,
            'tasks': 0,
            'saved': 0,
            'unchanged': 0,
            'error': 0,
            'skipped': 0,
            'success_rate': 0.0,
            'by_strategy': {},
            'quality_levels': {},
            'low_quality_sources': [],
            **extra,
        }

    runner = _make_runner(headless, timeout, max_concurrent)
    results = await runner.run_all(session, redis_client, task_ids=task_ids)
    await session.commit()

    summary = summarize_results(results)
    summary['job'] = job
    summary.update(extra)
    logger.info(
        '%s: задач=%s, успех=%.1f%%, стратегии=%s',
        job,
        summary['tasks'],
        summary['success_rate'] * 100,
        summary['by_strategy'],
    )
    return summary


# ============================================================================
# ЗАДАНИЯ СБОРА
# ============================================================================


async def collect_source(
    source: str,
    headless: bool = True,
    timeout: int | None = None,
    max_concurrent: int | None = None,
) -> dict[str, Any]:
    """Собрать один источник по всем активным конкурентам.

    Источник должен уже быть в БД — задание его НЕ создаёт: постановка
    нового источника на учёт требует категоризации и проверки поиска, это
    отдельное осознанное действие (:func:`register_source`). Если источник
    не найден, возвращается ``status='source_not_found'`` без побочных
    эффектов.

    Args:
        source: Источник в любой форме (``lenta.ru``, ``https://lenta.ru/``).
        headless: Запускать браузерные стратегии без окна.
        timeout: Таймаут парсинга, мс (по умолчанию из настроек).
        max_concurrent: Параллельных задач (по умолчанию из настроек).

    Returns:
        Сводка прогона (JSON-сериализуемая).
    """
    redis_client = await redis_client_instance.get_client()
    try:
        async with AsyncSessionLocal() as session:
            found = await _find_source(session, source)
            if found is None:
                logger.warning(
                    'Источник %s не найден в БД — сначала выполните '
                    'register_source()',
                    source,
                )
                return {
                    'job': 'collect_source',
                    'status': 'source_not_found',
                    'source': source,
                    'tasks': 0,
                }
            if not found.is_active:
                return {
                    'job': 'collect_source',
                    'status': 'source_inactive',
                    'source': found.name,
                    'source_id': found.id,
                    'tasks': 0,
                }

            competitor_ids = await _active_competitor_ids(session)
            task_ids = await _ensure_search_tasks(
                session, [found.id], competitor_ids
            )
            return await _run_and_summarize(
                job='collect_source',
                task_ids=task_ids,
                headless=headless,
                timeout=timeout,
                max_concurrent=max_concurrent,
                session=session,
                redis_client=redis_client,
                status='ok',
                source=found.name,
                source_id=found.id,
                competitors=len(competitor_ids),
            )
    finally:
        await redis_client_instance.close()


async def collect_competitor(
    competitor: str,
    inn: str | None = None,
    headless: bool = True,
    timeout: int | None = None,
    max_concurrent: int | None = None,
) -> dict[str, Any]:
    """Собрать одного конкурента по всем активным источникам.

    Конкурента, которого ещё нет в БД, задание создаёт само — в отличие от
    источника, здесь не нужны ни категоризация, ни проверка эндпоинта:
    достаточно названия (и опционально ИНН для поиска по госреестрам).

    Args:
        competitor: Название компании (например, ``Сбербанк``).
        inn: ИНН — нужен для поиска по гос. источникам (fedresurs и др.);
            без него такие источники задачу пропустят с ``not INN``.
        headless: Запускать браузерные стратегии без окна.
        timeout: Таймаут парсинга, мс (по умолчанию из настроек).
        max_concurrent: Параллельных задач (по умолчанию из настроек).

    Returns:
        Сводка прогона (JSON-сериализуемая).
    """
    redis_client = await redis_client_instance.get_client()
    try:
        async with AsyncSessionLocal() as session:
            name = (competitor or '').strip()
            if not name:
                return {
                    'job': 'collect_competitor',
                    'status': 'empty_competitor',
                    'tasks': 0,
                }

            stmt = select(Competitor).where(Competitor.name == name)
            found = (await session.execute(stmt)).scalar_one_or_none()
            created = False
            if found is None:
                found = Competitor(name=name, inn=inn or None)
                session.add(found)
                await session.flush()
                await session.commit()
                created = True
                logger.info('Конкурент %s создан (id=%s)', name, found.id)
            elif inn and not found.inn:
                # Дополняем ИНН, если его не было: это открывает гос.
                # источники, которые ищут именно по ИНН.
                found.inn = inn
                await session.commit()
                logger.info('У конкурента %s проставлен ИНН', name)

            # Проверка активности имеет смысл только для конкурента, который
            # уже был в БД: только что созданный активен по определению
            # (ActiveMixin.is_active по умолчанию True).
            if not created and not found.is_active:
                return {
                    'job': 'collect_competitor',
                    'status': 'competitor_inactive',
                    'competitor': found.name,
                    'competitor_id': found.id,
                    'tasks': 0,
                }

            source_ids = await _active_source_ids(session)
            task_ids = await _ensure_search_tasks(
                session, source_ids, [found.id]
            )
            return await _run_and_summarize(
                job='collect_competitor',
                task_ids=task_ids,
                headless=headless,
                timeout=timeout,
                max_concurrent=max_concurrent,
                session=session,
                redis_client=redis_client,
                status='ok',
                competitor=found.name,
                competitor_id=found.id,
                competitor_created=created,
                sources=len(source_ids),
            )
    finally:
        await redis_client_instance.close()


async def collect_all(
    headless: bool = True,
    timeout: int | None = None,
    max_concurrent: int | None = None,
    ensure_matrix: bool = True,
) -> dict[str, Any]:
    """Полный прогон: все активные источники × все активные конкуренты.

    Args:
        headless: Запускать браузерные стратегии без окна.
        timeout: Таймаут парсинга, мс (по умолчанию из настроек).
        max_concurrent: Параллельных задач (по умолчанию из настроек).
        ensure_matrix: Достроить недостающие связки источник-конкурент.
            ``True`` (по умолчанию) — «собрать всё» в буквальном смысле:
            каждая пара активных источника и конкурента будет пройдена.
            ``False`` — пройти только уже заведённые активные ``SearchTask``
            (режим «ничего не создавать в БД», полезен для планировщика,
            когда матрица ведётся вручную).

    Returns:
        Сводка прогона (JSON-сериализуемая).
    """
    redis_client = await redis_client_instance.get_client()
    try:
        async with AsyncSessionLocal() as session:
            source_ids = await _active_source_ids(session)
            competitor_ids = await _active_competitor_ids(session)

            if ensure_matrix:
                task_ids = await _ensure_search_tasks(
                    session, source_ids, competitor_ids
                )
            else:
                stmt = select(SearchTask.id).where(
                    SearchTask.is_active.is_(True),
                    SearchTask.source_id.in_(source_ids),
                    SearchTask.competitor_id.in_(competitor_ids),
                )
                task_ids = list((await session.execute(stmt)).scalars().all())

            return await _run_and_summarize(
                job='collect_all',
                task_ids=task_ids,
                headless=headless,
                timeout=timeout,
                max_concurrent=max_concurrent,
                session=session,
                redis_client=redis_client,
                status='ok',
                sources=len(source_ids),
                competitors=len(competitor_ids),
            )
    finally:
        await redis_client_instance.close()


async def register_source(url: str) -> dict[str, Any]:
    """Поставить новый источник на учёт.

    Нормализует ссылку до ``scheme://hostname/``, категоризирует сайт
    (тип, антибот-защита, CAPTCHA, SPA, рекомендованная стратегия),
    создаёт ``Source`` в БД (идемпотентно) и кладёт классификацию в кэш —
    дальше её переиспользует сбор, не вычисляя заново. Дополнительно
    проверяет, отвечает ли поисковый эндпоинт источника.

    Args:
        url: Ссылка на источник (``https://www.lenta.ru/news`` и т.п.).

    Returns:
        Результат регистрации (JSON-сериализуемый): нормализованное имя,
        hostname, признак создания, классификация и итог проверки поиска.
    """
    from src.bp1.adaptive.integration.sources import (
        SourceRegistrationService,
    )

    redis_client = await redis_client_instance.get_client()
    try:
        async with AsyncSessionLocal() as session:
            service = SourceRegistrationService(
                session, redis_client=redis_client
            )
            # probe_search=True: неработающий поиск видно сразу здесь, а не
            # при первой боевой задаче.
            result = await service.register(url, probe_search=True)
            await session.commit()

            probe = result.search_probe
            return {
                'job': 'register_source',
                'status': 'ok',
                'source': result.source_name,
                'host': result.host,
                'created': result.created,
                'source_id': result.source_id,
                'classification': result.classification.model_dump(mode='json'),
                'search_probe': (
                    probe.model_dump(mode='json') if probe else None
                ),
            }
    finally:
        await redis_client_instance.close()
