"""
AgenticOrchestrator — оркестрация стратегий обхода с деградацией.

Иерархия: FAST → CRAWL4AI → BROWSER → WAYBACK → HITL.
При ошибке или недостаточном объёме контента происходит переход
к следующей, более "тяжёлой" стратегии.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod

from core.config import settings

from ..schemas import StrategyResult, StrategyType

logger = logging.getLogger(__name__)

# Минимальная длина контента, при которой стратегия считается успешной.
MIN_CONTENT_LENGTH = settings.bp1_min_content_length

# Порядок стратегий при деградации.
_DEGRADATION_ORDER = (
    StrategyType.FAST,
    StrategyType.CRAWL4AI,
    StrategyType.BROWSER,
    StrategyType.WAYBACK,
    StrategyType.STEALTH,
    StrategyType.HITL,
)

# User-Agent по умолчанию для HTTP-стратегий.
_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0 Safari/537.36'
)


def _ssl_unverified_context():
    """Возвращает SSL-контекст без проверки сертификата.

    Гос. порталы и некоторые коммерческие сайты отдают самоподписанные /
    недоверенные сертификаты, из-за чего ``urllib.request`` бросает
    ``CERTIFICATE_VERIFY_FAILED`` и FAST-стратегия ложно падает. Контекст без
    верификации используется как fallback (аналогично ``ignore_https_errors``
    в браузерных стратегиях).
    """
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_sync(url: str, timeout_ms: int, user_agent: str) -> str:
    """Выполняет синхронный HTTP-запрос и возвращает тело ответа."""
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={'User-Agent': user_agent},
    )
    timeout = timeout_ms / 1000
    try:
        # Сначала обычный запрос с проверкой сертификата.
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception:
        # SSL/сертификат недоверенный — повторяем без верификации, чтобы
        # не ронять FAST-стратегию на гос.порталах с самоподписанными
        # сертификатами.
        with urllib.request.urlopen(
            req, timeout=timeout, context=_ssl_unverified_context()
        ) as resp:
            return resp.read().decode('utf-8', errors='replace')


class BaseStrategy(ABC):
    """Абстрактная стратегия обхода."""

    strategy_type: StrategyType

    @abstractmethod
    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        """Выполняет запрос и возвращает результат."""
        raise NotImplementedError


class FastStrategy(BaseStrategy):
    """Быстрая стратегия — прямой HTTP-запрос (стандартная библиотека)."""

    strategy_type = StrategyType.FAST

    def __init__(self, timeout_ms: int = 30000):
        self._timeout_ms = timeout_ms

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        try:
            html = await asyncio.to_thread(
                _fetch_sync, url, self._timeout_ms, _DEFAULT_USER_AGENT
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=len(html) >= MIN_CONTENT_LENGTH,
                data=html,
                content_length=len(html),
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )


class WaybackStrategy(BaseStrategy):
    """Стратегия через Internet Archive Wayback Machine."""

    strategy_type = StrategyType.WAYBACK

    def __init__(self, timeout_ms: int = 30000):
        self._timeout_ms = timeout_ms

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        try:
            # 1. Получаем ближайший снапшот из API Wayback Machine.
            api_url = f'https://archive.org/wayback/available?url={url}'
            api_json = await asyncio.to_thread(
                _fetch_sync, api_url, self._timeout_ms, _DEFAULT_USER_AGENT
            )
            snapshot_url = self._extract_snapshot_url(api_json)
            if not snapshot_url:
                return StrategyResult(
                    strategy=self.strategy_type,
                    success=False,
                    error='no wayback snapshot available',
                    elapsed_ms=int((time.monotonic() - start) * 1000),
                )

            # 2. Скачиваем сам HTML снапшота.
            html = await asyncio.to_thread(
                _fetch_sync,
                snapshot_url,
                self._timeout_ms,
                _DEFAULT_USER_AGENT,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=len(html) >= MIN_CONTENT_LENGTH,
                data=html,
                content_length=len(html),
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )

    @staticmethod
    def _extract_snapshot_url(api_json: str) -> str | None:
        """Извлекает URL снапшота из ответа API Wayback Machine."""
        import json

        try:
            data = json.loads(api_json)
            return (
                data.get('archived_snapshots', {}).get('closest', {}).get('url')
            )
        except (json.JSONDecodeError, AttributeError):
            return None


class BrowserStrategy(BaseStrategy):
    """Стратегия через Playwright (браузерная автоматизация)."""

    strategy_type = StrategyType.BROWSER

    def __init__(self, headless: bool = True, timeout_ms: int = 60000):
        self._headless = headless
        self._timeout_ms = timeout_ms

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        p = None
        browser = None
        try:
            from playwright.async_api import async_playwright

            p = await async_playwright().start()
            browser = await p.chromium.launch(headless=self._headless)
            # Игнорируем невалидные TLS-сертификаты (гос. порталы и др.
            # с самоподписанными/недоверенными сертификатами).
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            await page.goto(url, timeout=self._timeout_ms)
            html = await page.content()

            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=len(html) >= MIN_CONTENT_LENGTH,
                data=html,
                content_length=len(html),
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )
        finally:
            # Гарантированно освобождаем ресурсы даже при отмене корутины
            # (asyncio.wait_for / fetch_with_timeout). shield защищает
            # close()/stop() от отмены, чтобы процесс не завис.
            if browser is not None:
                try:
                    await asyncio.shield(browser.close())
                except Exception:
                    pass
            if p is not None:
                try:
                    await asyncio.shield(p.stop())
                except Exception:
                    pass


class AgenticOrchestrator:
    """
    Оркестратор стратегий обхода с автоматической деградацией.

    Иерархия: FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL.

    Использует реальные движки (crawl4ai, stealth, HITL) вместо заглушек.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 60000,
        profiles_dir: str = './src/bp1/data/profiles',
        logger: logging.Logger | None = None,
    ):
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._logger = logger or logging.getLogger(__name__)
        self._strategies: dict[StrategyType, BaseStrategy] = {}
        self._register_strategies(profiles_dir=profiles_dir)

    def _register_strategies(self, profiles_dir: str) -> None:
        """Регистрирует реальные стратегии обхода."""
        from .engines import build_default_strategies

        self._strategies = build_default_strategies(
            headless=self._headless,
            timeout_ms=self._timeout_ms,
            profiles_dir=profiles_dir,
            logger=self._logger,
        )

    def register_strategy(
        self, strategy_type: StrategyType, strategy: BaseStrategy
    ) -> None:
        """Регистрирует пользовательскую стратегию."""
        self._strategies[strategy_type] = strategy

    async def fetch_with_degradation(
        self,
        url: str,
        start_with: StrategyType | None = None,
        **kwargs,
    ) -> StrategyResult:
        """
        Выполняет запрос с автоматической деградацией.

        1. Пробует FAST (прямой HTTP-запрос)
        2. Если контент короче 300 символов → CRAWL4AI
        3. Если CRAWL4AI не сработал → BROWSER (Playwright)
        4. Если BROWSER не сработал → WAYBACK (Internet Archive)
        5. Если все стратегии не сработали → HITL (человек)
        """
        start_index = 0
        if start_with is not None:
            try:
                start_index = _DEGRADATION_ORDER.index(start_with)
            except ValueError:
                start_index = 0
            # start_with задаёт лишь начало перебора: проходим от start_with
            # до конца цепочки, а затем «догоняем» стратегии из начала,
            # не повторяя уже пройденные. Так при провале STEALTH будут
            # испробованы HITL и остальные стратегии (BROWSER/WAYBACK/FAST/
            # CRAWL4AI), а не только STEALTH → HITL.
            trailing = _DEGRADATION_ORDER[start_index:]
            leading = tuple(
                t for t in _DEGRADATION_ORDER[:start_index] if t not in trailing
            )
            # Оба слагаемых — tuple, чтобы не получить
            # "can only concatenate tuple (not 'list') to tuple".
            order = trailing + leading
        else:
            order = _DEGRADATION_ORDER

        for strategy_type in order:
            strategy = self._strategies.get(strategy_type)
            if strategy is None:
                continue

            self._logger.info(
                'Попытка стратегии %s для %s',
                strategy_type.value,
                url,
            )
            result = await strategy.fetch(url, **kwargs)

            if result.success:
                self._logger.info(
                    'Стратегия %s успешна для %s (контент=%d, '
                    'длительность=%d мс)',
                    strategy_type.value,
                    url,
                    result.content_length,
                    result.elapsed_ms,
                )
                return result

            self._logger.warning(
                'Стратегия %s не сработала для %s: %s',
                strategy_type.value,
                url,
                result.error,
            )

        # Все стратегии не сработали.
        return StrategyResult(
            strategy=StrategyType.HITL,
            success=False,
            error='all strategies failed',
        )

    async def fetch_with_timeout(
        self,
        url: str,
        timeout_ms: int = 30000,
        cleanup_timeout_s: float = 5.0,
        **kwargs,
    ) -> StrategyResult:
        """
        Выполняет запрос с глобальным таймаутом.

        В отличие от ``asyncio.wait_for``, при срабатывании таймаута задача
        отменяется и ожидается её полное завершение, чтобы стратегии успели
        корректно освободить ресурсы (закрыть браузер, потоки и т.п.).
        """
        task = asyncio.ensure_future(self.fetch_with_degradation(url, **kwargs))
        try:
            done, _ = await asyncio.wait({task}, timeout=timeout_ms / 1000)
            if task in done:
                return task.result()
        except asyncio.CancelledError:
            task.cancel()
            raise

        # Таймаут: отменяем задачу и ждём завершения cleanup.
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=cleanup_timeout_s)
        except (asyncio.CancelledError, TimeoutError, Exception):
            pass

        return StrategyResult(
            strategy=StrategyType.FAST,
            success=False,
            error=f'timeout after {timeout_ms}ms',
        )
