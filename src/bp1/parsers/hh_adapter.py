"""
Адаптер для api.hh.ru, реализующий интерфейс BaseParser.

Заглушка для тестирования интеграции с BP-1.
"""

import logging
import random

from ..base_parser import BaseParser, ParsedItem, ParsedResponse

logger = logging.getLogger(__name__)


class HHAdapter(BaseParser):
    """Адаптер-заглушка для HeadHunter API."""

    def __init__(self, **kwargs):
        logger.info('Инициализация HHAdapter')

    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        logger.info('Выполняется модуль парсинга: api.hh.ru')

        source = self.get_source_name()
        # Генерируем уникальный URL для заглушки, чтобы хэш отличался
        # при каждом вызове (иначе у всех пустых заглушек хэш одинаковый)
        stub_url = f'{source}{random.randint(1000, 9999)}'

        return ParsedResponse(
            meta={
                'source': source,
                'search_task_id': kwargs.get('search_task_id'),
                'competitor': kwargs.get('competitor'),
                'trigger': kwargs.get('trigger'),
            },
            items=[
                ParsedItem(
                    url=stub_url,
                    title='[stub] Заглушка',
                    text='Адаптер ещё не реализован',
                ),
            ],
        )

    def get_source_name(self) -> str:
        return 'https://api.hh.ru/'

    def get_parser_type(self) -> str:
        return 'api'
