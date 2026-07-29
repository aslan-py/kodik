from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from .browser import BrowserManager
from .config import get_human_delay, get_random_delay
from .constants import BASE_URL, MS_PER_SECOND, SELECTORS
from .exceptions import ElementNotFoundError, TimeoutExceededError
from .logger import get_logger
from .models import ParsingRequest, ParsingResult
from .utils import format_proxy_string, format_timestamp

logger = get_logger(__name__)


class KadArbitrParser:
    """RPA-парсер kad.arbitr.ru через Playwright."""

    def search_by_inn(self, request: ParsingRequest) -> ParsingResult:
        """Ищет дела по ИНН на kad.arbitr.ru и сохраняет HTML результат."""
        logger.info('Начало парсинга ИНН=%s', request.inn)

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        last_error: str | None = None
        for attempt in range(1, request.retry_count + 1):
            logger.info('Попытка %d/%d', attempt, request.retry_count)
            try:
                return self._attempt_parse(request, output_dir)
            except (ElementNotFoundError, TimeoutExceededError) as e:
                last_error = str(e)
                logger.warning('Попытка %d не удалась: %s', attempt, last_error)
                if attempt < request.retry_count:
                    delay = get_random_delay() * attempt
                    logger.info(
                        'Ожидание %.1fс перед следующей попыткой', delay
                    )
                    time.sleep(delay)
            except Exception as e:
                last_error = str(e)
                logger.error('Критическая ошибка: %s', last_error)
                return self._make_result(request, False, error=last_error)

        return self._make_result(
            request,
            False,
            error=f'Все попытки исчерпаны. Последняя ошибка: {last_error}',
        )

    def _attempt_parse(
        self, request: ParsingRequest, output_dir: Path
    ) -> ParsingResult:
        """Одна попытка парсинга."""
        with BrowserManager(
            headless=request.headless,
            proxy=request.proxy,
            user_agent=request.user_agent,
            timeout=request.timeout,
        ) as bm:
            page = bm.context.new_page()

            logger.info('Переход на %s', BASE_URL)
            page.goto(BASE_URL, wait_until='load')

            participant_input = page.locator(SELECTORS['participant_input'])
            try:
                participant_input.wait_for(
                    state='visible', timeout=request.timeout
                )
            except Exception as err:
                raise ElementNotFoundError(
                    "Поле 'Участник дела' не найдено"
                ) from err

            participant_input.click()
            participant_input.press_sequentially(request.inn, delay=50)
            logger.info('ИНН %s введён в поле', request.inn)

            page.wait_for_timeout(int(get_human_delay() * MS_PER_SECOND))

            search_button = page.locator(SELECTORS['search_button'])
            try:
                search_button.wait_for(state='visible', timeout=request.timeout)
            except Exception as err:
                raise ElementNotFoundError("Кнопка 'Найти' не найдена") from err
            search_button.click()
            logger.info("Кнопка 'Найти' нажата")

            results = page.locator(SELECTORS['results_container'])
            try:
                results.first.wait_for(
                    state='attached', timeout=request.timeout
                )
            except Exception as err:
                raise TimeoutExceededError(
                    f'Результаты не появились за {request.timeout}мс'
                ) from err
            logger.info('Результаты загружены')

            filename = f'kad_inn_{request.inn}_{format_timestamp()}.html'
            file_path = output_dir / filename
            file_path.write_text(page.content(), encoding='utf-8')
            logger.info('HTML сохранён: %s', file_path)

            time.sleep(get_random_delay())

            return self._make_result(
                request,
                True,
                file_path=str(file_path),
                user_agent=bm.user_agent,
            )

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
