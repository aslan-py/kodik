"""
Адаптер для kodik.ru/forum, реализующий интерфейс BaseParser.

Заглушка для тестирования интеграции с BP-1.
"""

import logging

from ..base_parser import BaseParser, ParsedResponse

logger = logging.getLogger(__name__)


class KodikForumAdapter(BaseParser):
    """Адаптер-заглушка для kodik.ru/forum."""

    def __init__(self, **kwargs):
        logger.info('Инициализация KodikForumAdapter')

    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        logger.info('Выполняется модуль парсинга: kodik.ru/forum')
        return ParsedResponse(
            meta={
                'source': self.get_source_name(),
                'search_task_id': kwargs.get('search_task_id'),
                'competitor': kwargs.get('competitor'),
                'trigger': kwargs.get('trigger'),
            },
            items=[],
        )

    def get_source_name(self) -> str:
        return 'https://kodik.ru/forum'

    def get_parser_type(self) -> str:
        return 'rpa'
