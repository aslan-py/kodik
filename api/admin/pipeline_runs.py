"""Read-only history of durable Celery pipeline executions."""

from fastadmin import register

from api.admin.base import MENU_PIPELINE_CONTROL, ReadOnlyModelAdmin
from core.database import AsyncSessionLocal
from core.pipeline.models import PipelineRun, PipelineStageRun


@register(PipelineRun, sqlalchemy_sessionmaker=AsyncSessionLocal)
class PipelineRunAdmin(ReadOnlyModelAdmin):
    """Recent manual and scheduled runs, ordered by creation time."""

    menu_section = MENU_PIPELINE_CONTROL
    verbose_name = 'Pipeline run'
    verbose_name_plural = 'Pipeline runs'
    list_display = (
        'run_id',
        'kind',
        'source',
        'status',
        'selected_stage',
        'root_task_id',
        'scheduled_for',
        'created_at',
        'started_at',
        'finished_at',
    )
    list_filter = ('kind', 'source', 'status')
    search_fields = ('run_id', 'root_task_id')
    ordering = ('-created_at',)


@register(PipelineStageRun, sqlalchemy_sessionmaker=AsyncSessionLocal)
class PipelineStageRunAdmin(ReadOnlyModelAdmin):
    """Per-stage details for a durable run, ordered BP1 through BP7."""

    menu_section = MENU_PIPELINE_CONTROL
    verbose_name = 'Pipeline stage run'
    verbose_name_plural = 'Pipeline stage details'
    list_display = (
        'pipeline_run',
        'stage',
        'status',
        'attempts',
        'reparse',
        'is_stub',
        'result',
        'task_id',
        'started_at',
        'finished_at',
    )
    list_select_related = ('pipeline_run',)
    list_filter = ('stage', 'status', 'is_stub', 'reparse')
    search_fields = ('task_id',)
    ordering = ('-created_at', 'stage')
