"""Ручной раннер конвейера BP-1…BP-7 — запуск по этапам, без Celery.

См. registry.py (карта этапов) и runner.py (сам запуск + preflight).

Реэкспорт models, чтобы PipelineControlMarker регистрировался в
Base.metadata при импорте пакета — нужно для Alembic autogenerate (тот же
приём, что и в src/bpN/__init__.py, см. src/db_registry.py).
"""

from core.pipeline.models import (
    PipelineControlMarker,
    PipelineRun,
    PipelineSchedule,
    PipelineStageRun,
)

__all__ = [
    'PipelineControlMarker',
    'PipelineRun',
    'PipelineSchedule',
    'PipelineStageRun',
]
