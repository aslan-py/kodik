"""
Адаптер для zakupki.gov.ru, реализующий интерфейс BaseParser.

Заглушка для тестирования интеграции с BP-1.
"""

import logging

from ..base_parser import BaseParser, ParsedResponse

logger = logging.getLogger(__name__)


class ZakupkiAdapter(BaseParser):
    """Адаптер-заглушка для Госзакупок."""

    def __init__(self, **kwargs):
        logger.info('Инициализация ZakupkiAdapter')

    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        logger.info('Выполняется модуль парсинга: zakupki.gov.ru')
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
        return 'https://zakupki.gov.ru/'

    def get_parser_type(self) -> str:
        return 'rpa'
