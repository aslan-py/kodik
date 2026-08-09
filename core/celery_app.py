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

from core.config import settings

# ===== Ретраи по умолчанию =====
# Дефолты для любой задачи, зарегистрированной через `app`, если она их не
# переопределяет явно.
CELERY_MAX_RETRIES: int = 3
"""Максимальное количество повторных попыток Celery-задачи."""

CELERY_DEFAULT_RETRY_DELAY: int = 60
"""Задержка перед повторной попыткой (сек)."""

CELERY_RETRY_BACKOFF_MAX: int = 600
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
    include=[
        # 'src.bp1.celery_tasks',
    ],
)

app.conf.timezone = 'UTC'
app.conf.beat_schedule = {}
