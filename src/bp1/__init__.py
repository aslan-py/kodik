"""BP-1 (слой сбора данных).

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
from .parsers import FedresursAdapter

# Runner - оркестратор пайплайна
from .runner import (
    BPRunner,
    RunMode,
    run_pipeline,
    run_pipeline_sync,
)
from .storage import RawDataService, calculate_content_hash
from .tasks import run_parser_async

__all__ = [
    'BPRunner',
    'BaseParser',
    'Competitor',
    'FedresursAdapter',
    'ParsedItem',
    'ParsedResponse',
    'ParserFactory',
    'RawDataService',
    'RawItem',
    'RunMode',
    'SearchTask',
    'Source',
    'Trigger',
    'calculate_content_hash',
    'run_parser_async',
    'run_parser_task',
    'run_pipeline',
    'run_pipeline_sync',
]
