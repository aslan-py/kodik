"""
Адаптер для fips.ru, реализующий интерфейс BaseParser.

Заглушка для тестирования интеграции с BP-1.
"""

import logging

from ..base_parser import BaseParser, ParsedResponse

logger = logging.getLogger(__name__)


class FipsAdapter(BaseParser):
    """Адаптер-заглушка для fips.ru."""

    def __init__(self, **kwargs):
        logger.info('Инициализация FipsAdapter')

    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        logger.info('Выполняется модуль парсинга: fips.ru')
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
        return 'https://www.fips.ru/'

    def get_parser_type(self) -> str:
        return 'rpa'
