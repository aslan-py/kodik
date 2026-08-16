"""Единое Celery-приложение проекта.

Все фоновые задачи любого BP регистрируются через `app` из этого модуля
(`from core.celery_app import app`), а не создают собственный `Celery()`.
Брокер и result backend — Redis на отдельных БД (см. core/config.py:
celery_broker_db/celery_result_backend_db), чтобы очередь не пересекалась
с бизнес-данными (например, дедуп-хэши BP-1 в redis_db).

`beat_schedule` заводится пустым — структура готова принимать периодические
задачи, но записей нет: расписывать конкретные BP-задачи под расписание —
предмет отдельных будущих изменений.
"""

from celery import Celery
from celery.signals import worker_process_init
from kombu import Exchange, Queue

from core.config import settings
from core.database import engine


@worker_process_init.connect
def dispose_inherited_sqlalchemy_pool(**_: object) -> None:
    """Give every prefork child its own asyncpg connections and event loop."""
    engine.sync_engine.dispose(close=False)


# ===== Ретраи по умолчанию =====
# Дефолты для любой задачи, зарегистрированной через `app`, если она их не
# переопределяет явно.
CELERY_MAX_RETRIES: int = settings.celery_task_max_retries
"""Максимальное количество повторных попыток Celery-задачи."""

CELERY_DEFAULT_RETRY_DELAY: int = (
    settings.celery_task_default_retry_delay_seconds
)
"""Задержка перед повторной попыткой (сек)."""

CELERY_RETRY_BACKOFF_MAX: int = settings.celery_task_retry_backoff_max_seconds
"""Максимальная задержка exponential backoff (сек)."""

app = Celery(
    'kodik',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend_url,
    # Модули с задачами регистрируются здесь явно (а не автообнаружением
    # по конвенции `<пакет>.tasks` — у BP-1 модуль называется celery_tasks.py):
    # процесс воркера импортирует только `app`, поэтому без этого списка
    # задачи остаются незарегистрированными, а `.delay()` из другого
    # процесса шлёт сообщение, которое некому обработать.
    include=['src.bp1.celery_tasks', 'core.pipeline.tasks'],
)

app.conf.update(
    timezone='UTC',
    enable_utc=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=CELERY_DEFAULT_RETRY_DELAY,
    task_default_queue='pipeline.stages',
    task_default_exchange='pipeline',
    task_default_exchange_type='direct',
    task_default_routing_key='pipeline.stages',
    task_queues=(
        Queue(
            'pipeline.control',
            Exchange('pipeline', type='direct'),
            routing_key='pipeline.control',
        ),
        Queue(
            'pipeline.bp1',
            Exchange('pipeline', type='direct'),
            routing_key='pipeline.bp1',
        ),
        Queue(
            'pipeline.stages',
            Exchange('pipeline', type='direct'),
            routing_key='pipeline.stages',
        ),
    ),
    task_routes={
        'src.bp1.celery_tasks.run_parser_task': {'queue': 'pipeline.bp1'},
        'core.pipeline.tasks.run_stage_bp1': {'queue': 'pipeline.bp1'},
        'core.pipeline.tasks.run_stage_bp2': {'queue': 'pipeline.stages'},
        'core.pipeline.tasks.run_stage_bp3': {'queue': 'pipeline.stages'},
        'core.pipeline.tasks.run_stage_bp4': {'queue': 'pipeline.stages'},
        'core.pipeline.tasks.run_stage_bp5': {'queue': 'pipeline.stages'},
        'core.pipeline.tasks.run_stage_bp6': {'queue': 'pipeline.stages'},
        'core.pipeline.tasks.run_stage_bp7': {'queue': 'pipeline.stages'},
        'core.pipeline.tasks.finalize_pipeline_run': {
            'queue': 'pipeline.control'
        },
        'core.pipeline.tasks.mark_pipeline_run_failed': {
            'queue': 'pipeline.control'
        },
        'core.pipeline.tasks.dispatch_scheduled_pipeline': {
            'queue': 'pipeline.control'
        },
        'core.pipeline.tasks.watch_stale_pipeline_runs': {
            'queue': 'pipeline.control'
        },
        'core.pipeline.tasks.reconcile_unpublished_pipeline_runs': {
            'queue': 'pipeline.control'
        },
    },
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
    task_time_limit=settings.celery_task_time_limit_seconds,
    beat_schedule={
        'pipeline-schedule-dispatcher': {
            'task': 'core.pipeline.tasks.dispatch_scheduled_pipeline',
            'schedule': settings.pipeline_schedule_poll_seconds,
            'options': {'queue': 'pipeline.control'},
        },
        'pipeline-stale-run-watchdog': {
            'task': 'core.pipeline.tasks.watch_stale_pipeline_runs',
            'schedule': settings.pipeline_schedule_poll_seconds,
            'options': {'queue': 'pipeline.control'},
        },
        'pipeline-unpublished-run-reconciler': {
            'task': 'core.pipeline.tasks.reconcile_unpublished_pipeline_runs',
            'schedule': settings.pipeline_schedule_poll_seconds,
            'options': {'queue': 'pipeline.control'},
        },
    },
)


REQUIRED_PIPELINE_TASKS = frozenset(
    {
        *(f'core.pipeline.tasks.run_stage_bp{stage}' for stage in range(1, 8)),
        'core.pipeline.tasks.finalize_pipeline_run',
        'core.pipeline.tasks.mark_pipeline_run_failed',
        'core.pipeline.tasks.reconcile_unpublished_pipeline_runs',
        'src.bp1.celery_tasks.run_parser_task',
    }
)


def validate_task_registration() -> None:
    """Fail worker startup diagnostics if a pipeline wrapper is missing."""
    app.loader.import_default_modules()
    missing = REQUIRED_PIPELINE_TASKS.difference(app.tasks)
    if missing:
        raise RuntimeError(
            'Missing required Celery task registrations: '
            + ', '.join(sorted(missing))
        )
    routes = app.conf.task_routes
    missing_routes = REQUIRED_PIPELINE_TASKS.difference(routes)
    if missing_routes:
        raise RuntimeError(
            'Missing required Celery task routes: '
            + ', '.join(sorted(missing_routes))
        )
