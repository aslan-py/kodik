# src/bp1/runner.py

"""
Единый runner для BP-1.

Режимы работы:
1. Тестовый (direct) — прямой запуск без Celery
2. Production (celery) — запуск через Celery задачи
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.redis_client import redis_client as redis_client_instance
from src.bp1.constants import (
    DEFAULT_MAX_CONCURRENT,
    DEFAULT_TIMEOUT_MS,
    LOG_SEPARATOR_WIDTH,
    MODE_CELERY,
    MODE_DIRECT,
    SEPARATOR_LINE,
    STATUS_ERROR,
    STATUS_QUEUED,
)
from src.bp1.models import SearchTask
from src.bp1.tasks import run_parser_async

logger = logging.getLogger(__name__)


class BPRunner:
    """
    Оркестратор для BP-1.

    Управляет запуском задач сбора данных.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = DEFAULT_TIMEOUT_MS,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ):
        self.headless = headless
        self.timeout = timeout
        self.max_concurrent = max_concurrent

    async def run_all(
        self,
        session: AsyncSession,
        redis_client,
        task_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Запустить все активные задачи.

        Args:
            session: Сессия БД
            redis_client: Клиент Redis
            task_ids: Список ID задач для запуска (если None — все активные)

        Returns:
            list[dict]: Результаты выполнения задач
        """
        # Получаем задачи
        if task_ids is None:
            tasks = await self._get_active_tasks(session)
        else:
            tasks = await self._get_tasks_by_ids(session, task_ids)

        if not tasks:
            logger.warning('Нет задач для выполнения')
            return []

        logger.info('Найдено задач: %d', len(tasks))
        logger.info('ID задач: %s', [t.id for t in tasks])

        results = []

        # Запускаем задачи последовательно (можно переделать на конкурентный)
        for idx, task in enumerate(tasks, 1):
            logger.info(SEPARATOR_LINE * LOG_SEPARATOR_WIDTH)
            logger.info('Задача %d/%d: ID=%d', idx, len(tasks), task.id)
            logger.info(SEPARATOR_LINE * LOG_SEPARATOR_WIDTH)

            result = await self._run_single_task(
                task.id,
                session,
                redis_client,
            )
            results.append(result)

        return results

    async def _get_active_tasks(
        self, session: AsyncSession
    ) -> list[SearchTask]:
        """Получить все активные задачи."""
        stmt = (
            select(SearchTask)
            .where(SearchTask.is_active.is_(True))
            .order_by(SearchTask.id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _get_tasks_by_ids(
        self,
        session: AsyncSession,
        task_ids: list[int],
    ) -> list[SearchTask]:
        """Получить задачи по списку ID."""
        stmt = (
            select(SearchTask)
            .where(SearchTask.id.in_(task_ids))
            .order_by(SearchTask.id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _run_single_task(
        self,
        task_id: int,
        session: AsyncSession,
        redis_client,
    ) -> dict[str, Any]:
        """Запустить одну задачу."""
        start_time = datetime.now()

        try:
            result = await run_parser_async(
                search_task_id=task_id,
                session=session,
                redis_client=redis_client,
                headless=self.headless,
                timeout=self.timeout,
            )

            elapsed = (datetime.now() - start_time).total_seconds()

            # Добавляем мета-информацию
            result['elapsed_seconds'] = elapsed
            result['task_id'] = task_id

            logger.info(
                'Задача %d: статус=%s, время=%.2f сек',
                task_id,
                result.get('status'),
                elapsed,
            )

            return result

        except Exception as e:
            logger.error('Задача %d: ошибка - %s', task_id, e, exc_info=True)
            return {
                'status': STATUS_ERROR,
                'task_id': task_id,
                'search_task_id': task_id,
                'error': str(e),
                'elapsed_seconds': (
                    datetime.now() - start_time
                ).total_seconds(),
            }


class RunMode:
    """Режимы запуска."""

    DIRECT = MODE_DIRECT  # Тестовый режим, прямой запуск
    CELERY = MODE_CELERY  # Production режим, через Celery


async def run_pipeline(
    mode: str = RunMode.DIRECT,
    task_ids: list[int] | None = None,
    headless: bool = True,
    timeout: int = DEFAULT_TIMEOUT_MS,
) -> list[dict[str, Any]]:
    """
    Основная точка входа для запуска BP-1.

    Args:
        mode: Режим запуска ('direct' или 'celery')
        task_ids: Список ID задач (если None — все активные)
        headless: Запускать браузер в headless режиме
        timeout: Таймаут для парсинга в мс

    Returns:
        list[dict]: Результаты выполнения
    """
    logger.info(SEPARATOR_LINE * LOG_SEPARATOR_WIDTH)
    logger.info('ЗАПУСК BP-1 PIPELINE')
    logger.info('Режим: %s', mode)
    logger.info(SEPARATOR_LINE * LOG_SEPARATOR_WIDTH)

    # Получаем Redis клиент
    redis = await redis_client_instance.get_client()

    try:
        if mode == RunMode.DIRECT:
            # Режим DIRECT: используем asyncio напрямую
            async with AsyncSessionLocal() as session:
                runner = BPRunner(
                    headless=headless,
                    timeout=timeout,
                )
                results = await runner.run_all(
                    session=session,
                    redis_client=redis,
                    task_ids=task_ids,
                )
                return results

        elif mode == RunMode.CELERY:
            # Режим CELERY: ставим задачи в Celery очередь
            # Здесь мы НЕ выполняем задачи синхронно,
            # а только отправляем их в Celery
            from src.bp1.celery_tasks import (
                run_parser_task,
            )  # импортируем позже

            results = []
            async with AsyncSessionLocal() as session:
                if task_ids is None:
                    tasks = await _get_active_task_ids(session)
                else:
                    tasks = task_ids

                logger.info('Отправка %d задач в Celery...', len(tasks))
                for task_id in tasks:
                    # Отправляем задачу в Celery
                    celery_result = run_parser_task.delay(
                        search_task_id=task_id,
                        headless=headless,
                        timeout=timeout,
                    )
                    results.append(
                        {
                            'task_id': task_id,
                            'celery_task_id': celery_result.id,
                            'status': STATUS_QUEUED,
                        }
                    )
                    logger.info(
                        'Задача %d отправлена в Celery (task_id=%s)',
                        task_id,
                        celery_result.id,
                    )

            return results

    finally:
        await redis_client_instance.close()


async def _get_active_task_ids(session: AsyncSession) -> list[int]:
    """Получить ID всех активных задач."""
    stmt = select(SearchTask.id).where(SearchTask.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ============================================================================
# Синхронная обертка для вызова из CLI
# ============================================================================


def run_pipeline_sync(
    mode: str = RunMode.DIRECT,
    task_ids: list[int] | None = None,
    headless: bool = True,
    timeout: int = DEFAULT_TIMEOUT_MS,
) -> list[dict[str, Any]]:
    """
    Синхронная обертка для запуска пайплайна.
    """
    return asyncio.run(
        run_pipeline(
            mode=mode,
            task_ids=task_ids,
            headless=headless,
            timeout=timeout,
        )
    )
