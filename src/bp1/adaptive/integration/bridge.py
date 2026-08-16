"""
AdaptiveBridgeParser — мост между Adaptive и BP-1 BaseParser.

Реализует BaseParser из bp1, используя AdaptiveParser для сбора данных
и конвертируя результат в ParsedResponse (совместимость с BP-1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.bp1.base_parser import BaseParser, ParsedItem, ParsedResponse

from ..processing.parser import AdaptiveParser


class AdaptiveBridgeParser(BaseParser):
    """
    Универсальный адаптер, реализующий BaseParser.

    Использует AdaptiveParser для сбора данных и конвертирует
    результат в ParsedResponse (совместимость с BP-1).
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        source_name: str = 'adaptive',
        redis_client: Any = None,
    ):
        self._adaptive_parser = AdaptiveParser(
            headless=headless, timeout=timeout, redis_client=redis_client
        )
        self._headless = headless
        self._timeout = timeout
        self._source_name = source_name

    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        """
        Выполняет адаптивный парсинг и возвращает ParsedResponse.

        Конвертация:
        - AdaptiveParseResult.items → ParsedResponse.items
        - meta формируется из kwargs (search_task_id, competitor, trigger)

        ``source_name`` для адаптера/классификации/профиля берётся из
        ``kwargs`` (реальный источник задачи), иначе из ``self._source_name``.
        Это гарантирует, что кэш привязывается к конкретному источнику, а не
        к общему имени ``'adaptive'``.
        """
        competitor = kwargs.get('competitor', '')
        trigger = kwargs.get('trigger', '')
        source_name = kwargs.get('source_name') or self._source_name

        result = await self._adaptive_parser.parse(
            url=url,
            source_name=source_name,
            competitor=competitor,
            trigger=trigger,
            expected_schema=kwargs.get('expected_schema'),
        )

        if result.status == 'error':
            raise RuntimeError(result.error or 'adaptive parse failed')

        items = [
            ParsedItem(
                # Полный абсолютный URL события (иначе не работает dedup_key
                # и media_domain в BP-2). Если ссылка относительная, она уже
                # превращена в абсолютную при извлечении.
                url=item.get('url', ''),
                title=item.get('title', '') or item.get('text', ''),
                text=item.get('text'),
                published_at=item.get('published_at'),
                region=item.get('region'),
                media_name=item.get('media_name'),
                # Поле trigger/competitor (для meta) не должно попадать в
                # items — они переносятся в meta (см. ниже).
                extra=item.get('extra', {}),
            )
            for item in result.items
        ]

        # Продвижение новостей (extra.news) в отдельные ParsedItem:
        # каждая статья из списка новостей поисковой страницы становится
        # самостоятельным событием с полным текстом (ex_text) в text.
        # Это позволяет BP-2 обрабатывать каждую новость отдельно.
        #
        # Оригинальные items и extra.news сохраняются (обратная совместимость
        # с потребителями, читающими extra['news']).
        promoted: list[ParsedItem] = []
        for base in items:
            news = base.extra.get('news') or []
            if news:
                base.extra['search_page'] = True
            for entry in news:
                if not isinstance(entry, dict):
                    continue
                ex_url = entry.get('ex_url', '')
                ex_title = entry.get('ex_title', '') or base.title
                ex_text = entry.get('ex_text')
                if not ex_url:
                    continue
                promoted.append(
                    ParsedItem(
                        url=ex_url,
                        title=ex_title,
                        text=ex_text,
                        published_at=None,
                        region=None,
                        media_name=base.media_name,
                        extra={
                            'news_source': 'adaptive_news',
                            # Parent (search) page.
                            'search_page_url': base.url,
                        },
                    )
                )

        items = items + promoted

        meta: dict[str, Any] = {
            'search_task_id': kwargs.get('search_task_id'),
            # Источник = реальный источник задачи, а не 'adaptive'.
            'source': source_name,
            'competitor': competitor,
            'trigger': trigger or None,
            # Ссылка на НАШ поисковый запрос (одна на всю выгрузку).
            'source_request_url': kwargs.get('source_request_url') or url,
            # Информация о пробинге (URL после поиска; если None — fallback).
            'probed_url': (
                kwargs.get('probed_url').search_url
                if kwargs.get('probed_url') is not None
                else None
            ),
            # Время съёма; в хэш НЕ включается, иначе всегда 'changed'.
            'fetched_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        }

        return ParsedResponse(meta=meta, items=items)

    def get_source_name(self) -> str:
        return self._source_name

    def get_parser_type(self) -> str:
        return 'adaptive'

    def bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к внутреннему парсеру."""
        self._adaptive_parser.bind_redis(redis_client)
