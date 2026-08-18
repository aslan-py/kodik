"""Тесты для network/throttle.py — HostThrottle: пауза между запросами
к одному хосту, независимость хостов друг от друга.
"""

import asyncio
import time

from src.bp1.network.throttle import HostThrottle


class TestFirstRequest:
    """Первый запрос к хосту не ждёт — истории ещё нет."""

    async def test_no_sleep_on_first_call(self, mocker):
        sleep_mock = mocker.patch('src.bp1.network.throttle.asyncio.sleep')
        throttle = HostThrottle(delay_seconds=2.0)

        await throttle.wait('lenta.ru')

        sleep_mock.assert_not_called()


class TestSecondRequestSameHost:
    """Второй запрос к тому же хосту ждёт остаток паузы."""

    async def test_waits_for_remaining_delay(self, mocker):
        sleep_mock = mocker.patch('src.bp1.network.throttle.asyncio.sleep')
        # Первый вызов: часы=100.0. Второй: часы=100.5 (прошло 0.5с из
        # требуемых 2.0с — ждать ещё 1.5с). Инъекция часов вместо патча
        # глобального time.monotonic — его использует и сам event loop.
        times = iter([100.0, 100.5])
        throttle = HostThrottle(delay_seconds=2.0, clock=lambda: next(times))

        await throttle.wait('lenta.ru')
        await throttle.wait('lenta.ru')

        sleep_mock.assert_called_once()
        (remaining,), _ = sleep_mock.call_args
        assert remaining == 1.5

    async def test_no_wait_if_delay_already_elapsed(self, mocker):
        sleep_mock = mocker.patch('src.bp1.network.throttle.asyncio.sleep')
        # Между вызовами прошло 5с — больше настроенной паузы 2с.
        times = iter([100.0, 105.0])
        throttle = HostThrottle(delay_seconds=2.0, clock=lambda: next(times))

        await throttle.wait('lenta.ru')
        await throttle.wait('lenta.ru')

        sleep_mock.assert_not_called()


class TestHostIndependence:
    """Разные хосты не делят состояние и не блокируют друг друга."""

    async def test_different_hosts_no_cross_wait(self, mocker):
        sleep_mock = mocker.patch('src.bp1.network.throttle.asyncio.sleep')
        throttle = HostThrottle(delay_seconds=2.0)

        await throttle.wait('lenta.ru')
        await throttle.wait('kommersant.ru')

        sleep_mock.assert_not_called()


class TestRealTiming:
    """Поведенческие тесты на реальных (небольших) задержках."""

    async def test_same_host_serializes_and_waits(self):
        throttle = HostThrottle(delay_seconds=0.15)

        start = time.monotonic()
        await throttle.wait('a')
        await throttle.wait('a')
        elapsed = time.monotonic() - start

        assert elapsed >= 0.15

    async def test_different_hosts_do_not_block_each_other(self):
        throttle = HostThrottle(delay_seconds=0.2)

        start = time.monotonic()
        await throttle.wait('a')
        await asyncio.gather(throttle.wait('a'), throttle.wait('b'))
        elapsed = time.monotonic() - start

        # wait('b') не ждёт паузу хоста 'a' — общее время близко к паузе
        # одного хоста, а не удваивается (0.2с + 0.2с).
        assert elapsed < 0.35
