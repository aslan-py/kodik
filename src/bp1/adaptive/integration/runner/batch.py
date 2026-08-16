"""Пакетный запуск задач сбора для ``AdaptiveRunner`` (run_all и связка)."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from src.bp1.models import Source


class _BatchMixin:
    """Методы ``AdaptiveRunner``, отвечающие за пакетный/конкурентный запуск.

    Примешивается к ``AdaptiveRunner`` (см. ``core.py``) — использует его
    ``run_task``, ``_bind_redis`` и атрибуты ``max_concurrent``,
    ``_session_factory``, ``_cache``, ``_logger``.
    """

    async def _record_source_failure(
        self,
        source_name: str,
        session: AsyncSession,
    ) -> None:
        """Зафиксировать полный отказ источника (all strategies failed).

        Двухуровневая логика (фича 1+2 circuit breaker):

        1. Блокируем источник в Redis на TTL circuit breaker (временная
           блокировка, чтобы не тратить ресурсы на повторные попытки).
        2. Инкрементируем счётчик подряд идущих отказов. Если он достиг
           ``settings.source_disable_threshold`` — отключаем ``Source``
           в БД (``is_active=False``) и сбрасываем счётчик.
        """
        ttl = settings.source_circuit_ttl_seconds
        threshold = settings.source_disable_threshold

        await self._cache.block_source(source_name, ttl=ttl)

        fail_count = await self._cache.increment_fail_count(source_name)
        self._logger.warning(
            'Источник %s недоступен, попытка отказа %d/%d (blocked %ss)',
            source_name,
            fail_count,
            threshold,
            ttl,
        )

        if fail_count >= threshold:
            stmt = select(Source).where(Source.name == source_name)
            source = (await session.execute(stmt)).scalar_one_or_none()
            if source is not None and source.is_active:
                source.is_active = False
                await session.commit()
                self._logger.warning(
                    'Источник %s отключён в БД (is_active=False) после '
                    '%d подряд отказов',
                    source_name,
                    fail_count,
                )
            await self._cache.reset_fail_count(source_name)

    async def run_all(
        self,
        session: AsyncSession,
        redis_client: Any,
        task_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Запустить все активные задачи.

        Учитываются флаги активности трёх уровней: сама SearchTask, её
        Source и Competitor. Если любой из них выключен (is_active=False),
        задача пропускается — адаптивный поиск ведётся только по активным
        источникам и конкурентам.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from src.bp1.models import SearchTask

        if task_ids:
            stmt = (
                select(SearchTask)
                .where(SearchTask.id.in_(task_ids))
                .options(
                    selectinload(SearchTask.source),
                    selectinload(SearchTask.competitor),
                )
            )
        else:
            stmt = (
                select(SearchTask)
                .where(SearchTask.is_active.is_(True))
                .options(
                    selectinload(SearchTask.source),
                    selectinload(SearchTask.competitor),
                )
            )

        result = await session.execute(stmt)
        tasks = result.scalars().all()

        # Разделяем задачи на пропущенные (решение принимается без запуска)
        # и запускаемые. Порядок результатов соответствует порядку задач —
        # важно для читаемости логов и потребителей run_all.
        results: list[dict[str, Any] | None] = [None] * len(tasks)
        runnable: list[tuple[int, int]] = []  # (позиция в results, task_id)
        for position, task in enumerate(tasks):
            if not task.source.is_active or not task.competitor.is_active:
                results[position] = {
                    'status': 'skipped',
                    'search_task_id': task.id,
                    'reason': (
                        'source_inactive'
                        if not task.source.is_active
                        else 'competitor_inactive'
                    ),
                }
                continue
            runnable.append((position, task.id))

        if runnable:
            if self.max_concurrent > 1:
                await self._run_tasks_concurrently(
                    runnable, results, redis_client
                )
            else:
                # Последовательный режим — прежнее поведение 1-в-1:
                # переиспользуем переданную сессию, ничего не создаём.
                for position, task_id in runnable:
                    results[position] = await self.run_task(
                        task_id, session, redis_client
                    )

        return [item for item in results if item is not None]

    async def _run_tasks_concurrently(
        self,
        runnable: list[tuple[int, int]],
        results: list[dict[str, Any] | None],
        redis_client: Any,
    ) -> None:
        """Выполняет задачи параллельно, записывая результаты по позициям.

        Ограничение параллелизма — ``self.max_concurrent`` (Шаг 17 плана
        рефакторинга, T1: параметр хранился в конфиге, но ``run_all``
        выполнял задачи последовательно).

        Каждая задача получает СВОЮ сессию БД: ``AsyncSession`` не
        рассчитана на одновременное использование несколькими корутинами
        (asyncpg падает с "another operation is in progress"), поэтому
        переданную в ``run_all`` сессию здесь переиспользовать нельзя —
        она остаётся только для выборки списка задач. Каждая сессия
        коммитится внутри ``RawDataService`` (см. ``storage.py``), так что
        результат не теряется при закрытии.

        Исключения не проглатываются: как и в последовательном режиме,
        первое из них поднимается наружу — но только после того, как все
        параллельные задачи завершились, чтобы не оставить висящих
        корутин с открытыми сессиями/браузерами.
        """
        if self._session_factory is None:
            from core.database import AsyncSessionLocal

            self._session_factory = AsyncSessionLocal

        semaphore = asyncio.Semaphore(self.max_concurrent)
        self._logger.info(
            'Запуск %d задач сбора (параллельно до %d)',
            len(runnable),
            self.max_concurrent,
        )

        async def _run_one(position: int, task_id: int) -> None:
            async with semaphore:
                async with self._session_factory() as task_session:
                    results[position] = await self.run_task(
                        task_id, task_session, redis_client
                    )

        outcomes = await asyncio.gather(
            *(_run_one(position, task_id) for position, task_id in runnable),
            return_exceptions=True,
        )
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome

    async def run_source_competitor(
        self,
        source: str,
        competitor: str,
        session: AsyncSession,
        redis_client: Any,
    ) -> dict[str, Any]:
        """Выполнить сбор для конкретной пары источник + конкурент.

        В отличие от run_all (который берёт все активные задачи из БД),
        этот метод строит отдельный запрос к БД по конкретному источнику
        и конкуренту:
        1. Находит или создаёт Source (по нормализованному имени).
        2. Находит или создаёт Competitor.
        3. Находит или создаёт SearchTask (связку без триггера).
        4. Запускает run_task для этой задачи.
        """
        from src.bp1.models import Competitor, SearchTask, Source

        from ..sources import SourceRegistrationService, normalize_source_url

        self._bind_redis(redis_client)

        # 1. Источник: ищем по нормализованному имени, иначе регистрируем.
        source_name = normalize_source_url(source)
        src_stmt = select(Source).where(Source.name == source_name)
        src = (await session.execute(src_stmt)).scalar_one_or_none()
        if src is None:
            reg = await SourceRegistrationService(
                session, redis_client=redis_client
            ).register(source)
            src_id = reg.source_id
            self._logger.info(
                'Источник %s зарегистрирован (source_id=%s)',
                source_name,
                src_id,
            )
        else:
            src_id = src.id
            # Адаптивный поиск ведётся только по активным источникам.
            if not src.is_active:
                return {
                    'status': 'skipped',
                    'reason': 'source_inactive',
                    'source': source_name,
                }

        # 2. Конкурент: ищем по имени, иначе создаём.
        comp_stmt = select(Competitor).where(Competitor.name == competitor)
        comp = (await session.execute(comp_stmt)).scalar_one_or_none()
        if comp is None:
            comp = Competitor(name=competitor)
            session.add(comp)
            await session.flush()
            self._logger.info(
                'Конкурент %s создан (id=%s)', competitor, comp.id
            )
        else:
            # Адаптивный поиск ведётся только по активным конкурентам.
            if not comp.is_active:
                return {
                    'status': 'skipped',
                    'reason': 'competitor_inactive',
                    'competitor': competitor,
                }

        # 3. SearchTask: ищем существующую связку без триггера, иначе создаём.
        task_stmt = select(SearchTask).where(
            SearchTask.source_id == src_id,
            SearchTask.competitor_id == comp.id,
            SearchTask.trigger_id.is_(None),
        )
        task = (await session.execute(task_stmt)).scalar_one_or_none()
        if task is None:
            task = SearchTask(
                source_id=src_id,
                competitor_id=comp.id,
                trigger_id=None,
                is_active=True,
            )
            session.add(task)
            await session.flush()
            self._logger.info(
                'Задача создана (search_task_id=%s) для source=%s',
                task.id,
                source_name,
            )
        await session.commit()

        # 4. Запускаем сбор.
        return await self.run_task(task.id, session, redis_client)
