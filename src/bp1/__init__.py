"""Модели BP-1 (слой сбора данных).

Реэкспорт моделей, чтобы они регистрировались в Base.metadata при импорте
пакета — нужно для Alembic autogenerate и create_all. Enum'ы живут в
core.enums.
"""

from src.bp1.models import (
    Competitor,
    RawItem,
    SearchTask,
    Source,
    Trigger,
)

from .base_parser import (
    BaseParser,
    ParsedItem,
    ParsedResponse,
    ParserFactory,
)
from .parsers import (
    FedresursAdapter,
    FipsAdapter,
    GoogleNewsAdapter,
    HHAdapter,
    KadArbitrAdapter,
    KodikForumAdapter,
    NicRuAdapter,
    VKAdapter,
    ZakupkiAdapter,
)
from .tasks import run_parser_async

__all__ = [
    'BaseParser',
    'Competitor',
    'FedresursAdapter',
    'FipsAdapter',
    'GoogleNewsAdapter',
    'HHAdapter',
    'KadArbitrAdapter',
    'KodikForumAdapter',
    'NicRuAdapter',
    'ParsedItem',
    'ParsedResponse',
    'ParserFactory',
    'RawItem',
    'RawItemStatus',
    'SearchTask',
    'Source',
    'Trigger',
    'VKAdapter',
    'ZakupkiAdapter',
    'run_parser_async',
]
