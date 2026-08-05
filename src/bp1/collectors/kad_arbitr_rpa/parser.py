"""RPA-парсер kad.arbitr.ru через Playwright (async)."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from .browser import BrowserManager
from .config import get_human_delay, get_random_delay
from .constants import BASE_URL, FILE_NAME_PREFIX, MS_PER_SECOND, SELECTORS
from .exceptions import ElementNotFoundError, TimeoutExceededError
from .schemas import ParsingRequest, ParsingResult
from .utils import format_proxy_string, format_timestamp

_testing_root = str(Path(__file__).resolve().parent.parent)
if _testing_root not in sys.path:
    sys.path.insert(0, _testing_root)

logger = logging.getLogger(__name__)


class KadArbitrParser:
    """RPA-парсер kad.arbitr.ru через Playwright (async)."""

    async def search_by_inn(self, request: ParsingRequest) -> ParsingResult:
        """Ищет дела по ИНН на kad.arbitr.ru и сохраняет HTML результат."""
        logger.info('Начало парсинга ИНН=%s', request.inn)

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        last_error: str | None = None
        for attempt in range(1, request.retry_count + 1):
            logger.info('Попытка %d/%d', attempt, request.retry_count)
            try:
                return await self._attempt_parse(request, output_dir)
            except (ElementNotFoundError, TimeoutExceededError) as e:
                last_error = str(e)
                logger.warning('Попытка %d не удалась: %s', attempt, last_error)
                if attempt < request.retry_count:
                    delay = get_random_delay() * attempt
                    logger.info(
                        'Ожидание %.1fс перед следующей попыткой', delay
                    )
                    await asyncio.sleep(delay)
            except Exception as e:
                last_error = str(e)
                logger.error('Критическая ошибка: %s', last_error)
                return self._make_result(request, False, error=last_error)

        return self._make_result(
            request,
            False,
            error=f'Все попытки исчерпаны. Последняя ошибка: {last_error}',
        )

    async def _attempt_parse(
        self, request: ParsingRequest, output_dir: Path
    ) -> ParsingResult:
        """Одна попытка парсинга."""
        bm = BrowserManager(
            headless=request.headless,
            proxy=request.proxy,
            user_agent=request.user_agent,
            timeout=request.timeout,
            use_stealth=request.use_stealth,
        )
        await bm.start()
        try:
            page = await bm.context.new_page()

            logger.info('Переход на %s', BASE_URL)
            await page.goto(BASE_URL, wait_until='load')

            # === Шаг 1: Заполнение поля "Участник дела" ===
            participant_input = page.locator(SELECTORS['participant_input'])
            try:
                await participant_input.wait_for(
                    state='visible', timeout=request.timeout
                )
            except Exception as err:
                raise ElementNotFoundError(
                    "Поле 'Участник дела' не найдено"
                ) from err

            await participant_input.fill(request.inn)
            logger.info('ИНН %s введён в поле', request.inn)

            await page.wait_for_timeout(int(get_human_delay() * MS_PER_SECOND))

            # === Шаг 2: Выбор типа участника "Любой" ===
            # Клик по 4-му элементу i для открытия дропдауна
            type_dropdown = page.locator('i').nth(4)
            try:
                await type_dropdown.wait_for(state='visible', timeout=5000)
                await type_dropdown.click()
            except Exception:
                logger.warning('Не удалось открыть дропдаун типа участника')

            await page.wait_for_timeout(300)

            # Фокус на span "Любой"
            type_span = page.locator('span').filter(has_text='Любой').first
            try:
                await type_span.wait_for(state='visible', timeout=5000)
                await type_span.click()
            except Exception:
                logger.warning("Не удалось кликнуть по span 'Любой'")

            await page.wait_for_timeout(300)

            # Выбор пункта "Любой" в списке
            type_item = (
                page.get_by_role('listitem').filter(has_text='Любой').first
            )
            try:
                await type_item.wait_for(state='visible', timeout=5000)
                await type_item.click()
            except Exception:
                logger.warning("Не удалось выбрать пункт 'Любой'")

            await page.wait_for_timeout(int(get_human_delay() * MS_PER_SECOND))

            # === Шаг 3: Нажатие кнопки "Найти" ===
            search_button = page.locator(SELECTORS['search_button'])
            try:
                await search_button.wait_for(
                    state='visible', timeout=request.timeout
                )
            except Exception as err:
                raise ElementNotFoundError("Кнопка 'Найти' не найдена") from err

            await search_button.click()
            logger.info("Кнопка 'Найти' нажата")

            # === Шаг 4: Ожидание загрузки результатов ===
            results = page.locator(SELECTORS['results_container'])
            try:
                await results.first.wait_for(
                    state='attached', timeout=request.timeout
                )
            except Exception as err:
                raise TimeoutExceededError(
                    f'Результаты не появились за {request.timeout}мс'
                ) from err
            logger.info('Результаты загружены')

            filename = (
                f'{FILE_NAME_PREFIX}{request.inn}_{format_timestamp()}.html'
            )
            file_path = output_dir / filename
            file_path.write_text(await page.content(), encoding='utf-8')
            logger.info('HTML сохранён: %s', file_path)

            await asyncio.sleep(get_random_delay())

            return self._make_result(
                request,
                True,
                file_path=str(file_path),
                user_agent=bm.user_agent,
            )
        finally:
            await bm.stop()

    def _make_result(
        self,
        request: ParsingRequest,
        success: bool,
        *,
        file_path: str | None = None,
        error: str | None = None,
        user_agent: str | None = None,
    ) -> ParsingResult:
        """Формирует ParsingResult с единообразным заполнением полей."""
        return ParsingResult(
            success=success,
            inn=request.inn,
            file_path=file_path,
            error=error,
            timestamp=datetime.now(),
            proxy_used=(
                format_proxy_string(
                    request.proxy.server, request.proxy.username
                )
                if request.proxy
                else None
            ),
            user_agent_used=user_agent,
        )
