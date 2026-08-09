"""
Реальные движки стратегий обхода (BP-1 Adaptive).

Реализует полноценные стратегии вместо заглушек:

- ``Crawl4AIStrategy`` — AI-краулинг через фреймворк ``crawl4ai``.
- ``StealthStrategy`` — обход антибот-защиты через существующий пакет
  ``src.bp1.collectors.stealth`` (инъекция стелса + обход QRATOR).
- ``HITLStrategy`` — Human-in-the-Loop: запуск видимого браузера,
  ожидание решения CAPTCHA человеком и кэширование профиля.

Все стратегии наследуют ``BaseStrategy`` и возвращают ``StrategyResult``,
что позволяет оркестратору использовать их в единой иерархии деградации.
"""

from __future__ import annotations

import logging
import time

from ..schemas import StrategyResult, StrategyType
from .hitl import HITLManager
from .orchestrator import MIN_CONTENT_LENGTH, BaseStrategy

logger = logging.getLogger(__name__)


class Crawl4AIStrategy(BaseStrategy):
    """
    Стратегия AI-краулинга через фреймворк ``crawl4ai``.

    Использует ``AsyncWebCrawler`` для извлечения контента с поддержкой
    JavaScript-рендеринга и автоматического извлечения структуры.
    """

    strategy_type = StrategyType.CRAWL4AI

    def __init__(
        self,
        timeout_ms: int = 60000,
        logger: logging.Logger | None = None,
    ):
        self._timeout_ms = timeout_ms
        self._logger = logger or logging.getLogger(__name__)

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        try:
            from crawl4ai import (
                AsyncWebCrawler,
                BrowserConfig,
                CrawlerRunConfig,
            )

            browser_config = BrowserConfig(headless=True)
            run_config = CrawlerRunConfig(
                page_timeout=self._timeout_ms,
                wait_until='domcontentloaded',
            )
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

            html = result.html if result and result.html else ''
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
            self._logger.warning('Crawl4AI не сработал для %s: %s', url, e)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )


class StealthStrategy(BaseStrategy):
    """
    Стратегия обхода антибот-защиты через ``collectors.stealth``.

    Запускает Playwright с инъекцией стелса (``apply_stealth``),
    антидетект-аргументами запуска и обходом QRATOR при необходимости.
    """

    strategy_type = StrategyType.STEALTH

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 60000,
        logger: logging.Logger | None = None,
    ):
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._logger = logger or logging.getLogger(__name__)

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        try:
            from playwright.async_api import async_playwright

            from src.bp1.collectors.stealth import (
                apply_stealth,
                bypass_qrator,
                get_context_config,
                get_launch_args,
            )

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self._headless,
                    args=get_launch_args(headless=self._headless),
                )
                context_config = get_context_config()
                # Игнорируем невалидные/самоподписанные TLS-сертификаты
                # (zakupki.gov.ru и др. гос. порталы отдают
                # ERR_CERT_AUTHORITY_INVALID).
                context_config.setdefault('ignore_https_errors', True)
                context = await browser.new_context(**context_config)
                await apply_stealth(context)
                page = await context.new_page()
                response = await page.goto(url, timeout=self._timeout_ms)
                status = response.status if response else 0

                # При 401/403 пробуем обойти QRATOR-защиту.
                if status in (401, 403):
                    await bypass_qrator(
                        page, context, target_url=url, timeout=self._timeout_ms
                    )

                html = await page.content()
                await context.close()
                await browser.close()

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
            self._logger.warning('Stealth не сработал для %s: %s', url, e)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )


class HITLStrategy(BaseStrategy):
    """
    Human-in-the-Loop стратегия.

    При недоступности автоматических стратегий запускает видимый браузер
    и ожидает, пока человек решит CAPTCHA. Результат (cookies) кэшируется
    в профиль для повторного использования.
    """

    strategy_type = StrategyType.HITL

    def __init__(
        self,
        profiles_dir: str = './src/bp1/data/profiles',
        timeout_s: int = 120,
        logger: logging.Logger | None = None,
    ):
        self._hitl = HITLManager(profiles_dir=profiles_dir, logger=logger)
        self._timeout_s = timeout_s
        self._logger = logger or logging.getLogger(__name__)

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        start = time.monotonic()
        source_name = kwargs.get('source_name', 'unknown')
        try:
            response = await self._hitl.handle_challenge(
                url=url,
                source_name=source_name,
                challenge_type='captcha',
                timeout_s=self._timeout_s,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            if response.success:
                # После решения CAPTCHA передаём HTML страницы дальше
                # в пайплайн (раньше возвращался пустой data).
                html = response.html or ''
                if len(html) < MIN_CONTENT_LENGTH:
                    # Профиль найден, но страница не загрузилась (например,
                    # TLS-ошибка при использовании закэшированных cookies).
                    # Возвращаем осмысленную ошибку, а не ложный успех.
                    return StrategyResult(
                        strategy=self.strategy_type,
                        success=False,
                        error=(
                            'HITL profile found but page returned empty '
                            'content (likely TLS/network issue)'
                        ),
                        content_length=len(html),
                        elapsed_ms=elapsed,
                    )
                return StrategyResult(
                    strategy=self.strategy_type,
                    success=len(html) >= MIN_CONTENT_LENGTH,
                    data=html,
                    content_length=len(html),
                    elapsed_ms=elapsed,
                )
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=response.error or 'challenge requires human interaction',
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            self._logger.warning('HITL не сработал для %s: %s', url, e)
            return StrategyResult(
                strategy=self.strategy_type,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )


def build_default_strategies(
    headless: bool = True,
    timeout_ms: int = 60000,
    profiles_dir: str = './src/bp1/data/profiles',
    logger: logging.Logger | None = None,
) -> dict[StrategyType, BaseStrategy]:
    """
    Собрать словарь реальных стратегий по умолчанию.

    Возвращает все стратегии иерархии деградации с реальными реализациями
    (без заглушек): FAST, CRAWL4AI, BROWSER, WAYBACK, STEALTH, HITL.
    """
    from .orchestrator import (
        BrowserStrategy,
        FastStrategy,
        WaybackStrategy,
    )

    logger = logger or logging.getLogger(__name__)
    return {
        StrategyType.FAST: FastStrategy(timeout_ms=timeout_ms),
        StrategyType.CRAWL4AI: Crawl4AIStrategy(
            timeout_ms=timeout_ms, logger=logger
        ),
        StrategyType.BROWSER: BrowserStrategy(
            headless=headless, timeout_ms=timeout_ms
        ),
        StrategyType.WAYBACK: WaybackStrategy(timeout_ms=timeout_ms),
        StrategyType.STEALTH: StealthStrategy(
            headless=headless, timeout_ms=timeout_ms, logger=logger
        ),
        StrategyType.HITL: HITLStrategy(
            profiles_dir=profiles_dir, logger=logger
        ),
    }
