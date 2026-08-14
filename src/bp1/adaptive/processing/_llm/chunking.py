"""Оркестрация параллельной обработки с ограничением параллелизма (BP-1
Adaptive).

Изначально использовалась только для чанков ``StructuredChunker``
(``LLMClient``), но сама по себе не завязана на ``Chunk`` — сигнатура
обобщена (Шаг 14 плана рефакторинга, REFACTORING_PLAN.md), чтобы её мог
переиспользовать и батчинг ``AIAgent.score_relevance`` (пачки элементов,
а не чанки HTML), не дублируя логику ограничения параллелизма/сбора
результатов.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable


async def run_limited[TIn, TOut](
    items: list[TIn],
    worker: Callable[[TIn], Awaitable[TOut]],
    parallel_workers: int,
    logger: logging.Logger,
    error_msg: str,
) -> list[TOut]:
    """Параллельно обрабатывает элементы с ограничением параллелизма.

    Args:
        items: Список элементов (чанки, пачки и т.п.).
        worker: Асинхронная функция обработки одного элемента.
        parallel_workers: Максимальное число одновременных запросов.
        logger: Логгер для записи ошибок.
        error_msg: Шаблон сообщения об ошибке (подставляется объект).

    Returns:
        list[TOut]: Список успешных результатов (ошибки отброшены
            и залогированы) — если ``worker`` сама перехватывает свои
            исключения и не бросает их наружу (как это делает батчинг
            релевантности, деградируя на эвристику внутри воркера), длина
            результата совпадает с длиной ``items``.
    """
    if not items:
        return []

    semaphore = asyncio.Semaphore(max(1, parallel_workers))

    async def _limited(item: TIn) -> TOut:
        async with semaphore:
            return await worker(item)

    tasks = [_limited(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid: list[TOut] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning(error_msg, result)
            continue
        valid.append(result)
    return valid
