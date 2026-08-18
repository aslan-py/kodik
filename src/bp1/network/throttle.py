"""Троттлинг запросов по hostname для RPA-стратегий сбора BP-1.

Внутрипроцессная пауза между последовательными запросами к одному хосту
(не распределённая между процессами — design.md изменения
``add-rpa-collection-proxying``, решение D7: при
``celery_bp1_worker_concurrency=1`` по умолчанию этого достаточно;
если параллелизм BP-1 когда-нибудь вырастет, троттлинг нужно будет
вынести на Redis отдельным изменением).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from core.config import settings


class HostThrottle:
    """Выдерживает минимальную паузу между запросами к одному хосту.

    Запросы к разным хостам друг друга не блокируют — у каждого хоста
    своя блокировка (создаётся лениво при первом обращении).
    """

    def __init__(
        self,
        delay_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._delay_seconds = (
            delay_seconds
            if delay_seconds is not None
            else settings.bp1_rpa_request_delay_seconds
        )
        # Инъекция часов — тестам не нужно подменять глобальный
        # time.monotonic (он общий на процесс и используется внутренними
        # механизмами asyncio, включая event loop).
        self._clock = clock
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()
        self._last_request_at: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        """Дождаться истечения паузы с последнего запроса к ``host``,
        затем зафиксировать текущий запрос как последний.
        """
        lock = await self._lock_for(host)
        async with lock:
            now = self._clock()
            last = self._last_request_at.get(host)
            if last is None:
                self._last_request_at[host] = now
                return

            remaining = self._delay_seconds - (now - last)
            if remaining > 0:
                await asyncio.sleep(remaining)
                # Расчётное время слота, а не новое monotonic() после сна —
                # не накапливает дрейф от превышения фактическим sleep()
                # запрошенной длительности.
                self._last_request_at[host] = last + self._delay_seconds
            else:
                self._last_request_at[host] = now

    async def _lock_for(self, host: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(host)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[host] = lock
            return lock


# Общий на процесс троттлер для RPA-стратегий (см. design.md, D4/D7).
default_throttle = HostThrottle()
