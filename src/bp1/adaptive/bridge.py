"""
AdaptiveBridgeParser — мост между Adaptive и BP-1 BaseParser.

Реализует BaseParser из bp1, используя AdaptiveParser для сбора данных
и конвертируя результат в ParsedResponse (совместимость с BP-1).
"""

from __future__ import annotations

from typing import Any

from src.bp1.base_parser import BaseParser, ParsedItem, ParsedResponse

from .parser import AdaptiveParser


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
        """
        competitor = kwargs.get('competitor', '')
        trigger = kwargs.get('trigger', '')

        result = await self._adaptive_parser.parse(
            url=url,
            source_name=self._source_name,
            competitor=competitor,
            trigger=trigger,
            expected_schema=kwargs.get('expected_schema'),
        )

        if result.status == 'error':
            raise RuntimeError(result.error or 'adaptive parse failed')

        items = [
            ParsedItem(
                url=item.get('url', ''),
                title=item.get('title', ''),
                text=item.get('text'),
                published_at=item.get('published_at'),
                region=item.get('region'),
                media_name=item.get('media_name'),
                extra=item.get('extra', {}),
            )
            for item in result.items
        ]

        meta: dict[str, Any] = {
            'search_task_id': kwargs.get('search_task_id'),
            'source': self._source_name,
            'competitor': competitor,
            'trigger': trigger,
            'source_request_url': kwargs.get('source_request_url', url),
            'strategy_used': result.strategy_used.value,
            'trace_id': result.trace_id,
        }

        return ParsedResponse(meta=meta, items=items)

    def get_source_name(self) -> str:
        return self._source_name

    def get_parser_type(self) -> str:
        return 'adaptive'

    def bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к внутреннему парсеру."""
        self._adaptive_parser.bind_redis(redis_client)
