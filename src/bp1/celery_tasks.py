# src/bp1/celery_tasks.py

"""
Celery задачи для BP-1.
"""

import asyncio
import logging
from typing import Any

from celery import shared_task

from core.database import AsyncSessionLocal
from core.redis_client import redis_client as redis_client_instance
from src.bp1.constants import (
    CELERY_DEFAULT_RETRY_DELAY,
    CELERY_MAX_RETRIES,
    CELERY_RETRY_BACKOFF_MAX,
    DEFAULT_TIMEOUT_MS,
)
from src.bp1.tasks import run_parser_async

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=CELERY_MAX_RETRIES,
    default_retry_delay=CELERY_DEFAULT_RETRY_DELAY,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=CELERY_RETRY_BACKOFF_MAX,
    retry_jitter=True,
)
def run_parser_task(
    self,
    search_task_id: int,
    headless: bool = True,
    timeout: int = DEFAULT_TIMEOUT_MS,
) -> dict[str, Any]:
    """
    Celery задача для парсинга одного источника.

    Используется в production режиме.
    """
    logger.info('Celery task started: search_task_id=%s', search_task_id)

    # В Celery нужно использовать asyncio.run()
    async def _run():
        redis = await redis_client_instance.get_client()
        try:
            async with AsyncSessionLocal() as session:
                result = await run_parser_async(
                    search_task_id=search_task_id,
                    session=session,
                    redis_client=redis,
                    headless=headless,
                    timeout=timeout,
                )
                return result
        finally:
            await redis_client_instance.close()

    try:
        result = asyncio.run(_run())
        logger.info('Celery task finished: %s', result.get('status'))
        return result
    except Exception as e:
        logger.error('Celery task failed: %s', e, exc_info=True)
        # Повторный вызов с задержкой
        raise self.retry(exc=e) from e
