"""Оркестрация параллельного чанкированного LLM-анализа (BP-1 Adaptive).

Содержит вспомогательные функции для параллельного извлечения структуры
из чанков: ограничение параллелизма через семафор и сбор результатов
с отбрасыванием ошибок. Используется ``LLMClient``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from ..chunker import Chunk


async def run_limited[T](
    items: list[Chunk],
    worker: Callable[[Chunk], Awaitable[T]],
    parallel_workers: int,
    logger: logging.Logger,
    error_msg: str,
) -> list[T]:
    """Параллельно обрабатывает чанки с ограничением параллелизма.

    Args:
        items: Список чанков.
        worker: Асинхронная функция обработки одного чанка.
        parallel_workers: Максимальное число одновременных запросов.
        logger: Логгер для записи ошибок.
        error_msg: Шаблон сообщения об ошибке (подставляется объект).

    Returns:
        list[_T]: Список успешных результатов (ошибки отброшены
            и залогированы).
    """
    if not items:
        return []

    semaphore = asyncio.Semaphore(max(1, parallel_workers))

    async def _limited(chunk: Chunk) -> T:
        async with semaphore:
            return await worker(chunk)

    tasks = [_limited(chunk) for chunk in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid: list[T] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning(error_msg, result)
            continue
        valid.append(result)
    return valid
