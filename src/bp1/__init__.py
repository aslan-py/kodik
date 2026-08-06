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

# Celery задачи (для production режима)
from .celery_tasks import run_parser_task
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

# Runner - оркестратор пайплайна
from .runner import (
    BPRunner,
    RunMode,
    run_pipeline,
    run_pipeline_sync,
)
from .tasks import run_parser_async

# CLI интерфейс (импортируется для удобства, но не экспортируется)
# from .cli import main

__all__ = [
    'BPRunner',
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
    'RunMode',
    'SearchTask',
    'Source',
    'Trigger',
    'VKAdapter',
    'ZakupkiAdapter',
    'create_runner',
    'run_parser_async',
    'run_parser_task',
    'run_pipeline',
    'run_pipeline_sync',
]
