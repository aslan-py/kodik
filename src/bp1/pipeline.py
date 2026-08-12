"""Конвейер BP-1: сбор данных из внешних источников -> raw_item.

Единственный этап пайплайна без собственных "смыслов" — просто обходит
активные задачи сбора (`search_task`) и складывает снимки в сырьевой слой,
откуда их читает нормализация BP-2 (`split_items` разбирает `raw_data` по
тому же контракту, что уже строит `AdaptiveBridgeParser`).

Порядок шагов:

  1. досоздать задачи без поискового слова для всех активных пар
     «конкурент × источник» — sync_search_task_coverage
  2. взять все активные задачи сбора — AdaptiveRunner.run_all (учитывает
     активность самой задачи, её источника и конкурента)
  3. по каждой задаче: классифицировать источник, распознать структуру,
     извлечь события, провалидировать качество — src/bp1/adaptive/
  4. сохранить результат в RawItem с дедупликацией по хэшу содержимого
     (Redis) — RawDataService.persist (src/bp1/storage.py)
  5. свернуть результаты по задачам в сводку прогона — _summarize

Оркестратор run_bp1 открывает сессию и Redis-клиент один раз на весь
прогон, коммитит сессию и закрывает Redis в finally — по образцу
src/bp1/runner.py::run_pipeline (более старой, direct/celery обвязки,
которую этот модуль не заменяет и не переиспользует).

Соседние модули: src/bp1/adaptive/integration/runner.py — AdaptiveRunner,
сам оркестратор сбора по одной задаче (run_task) и по всем активным
(run_all); src/bp1/storage.py — персистентность (RawDataService).

Заглушка этапа 1 (минимальный синтетический набор для дешёвой сквозной
проверки конвейера, без сети и LLM) живёт отдельно —
core/scripts/stages/bp1_stub.py. Какая из двух реализаций выполняется —
решает core/pipeline/registry.py по настройке TRUE_PARSING.
"""

from typing import Any

from core.config import settings
from core.database import AsyncSessionLocal
from core.redis_client import redis_client as redis_client_instance
from src.bp1.adaptive.integration.runner import AdaptiveRunner
from src.bp1.search_task_coverage import sync_search_task_coverage

# Статусы результата одной задачи (run_task/persist), которые считаем
# отдельно в сводке; всё остальное ('skipped', 'source_inactive',
# 'competitor_inactive', 'source_unavailable' и т.п.) — общий "пропущено".
_STATUS_SAVED = 'saved'
_STATUS_UNCHANGED = 'unchanged'
_STATUS_ERROR = 'error'


def _summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    """Свернуть результаты по задачам сбора в сводку прогона.

    saved — создан новый снимок; unchanged — источник не изменился с
    прошлого прогона (дедуп по хэшу в Redis); error — сбой обхода
    источника; skipped — задача/источник/конкурент неактивны либо источник
    временно заблокирован circuit breaker'ом. Ни одна из этих причин не
    прерывает обработку остальных задач (см. run_task/run_all).
    """
    summary = {
        'tasks': len(results),
        'saved': 0,
        'unchanged': 0,
        'error': 0,
        'skipped': 0,
    }
    for result in results:
        status = result.get('status')
        if status == _STATUS_SAVED:
            summary['saved'] += 1
        elif status == _STATUS_UNCHANGED:
            summary['unchanged'] += 1
        elif status == _STATUS_ERROR:
            summary['error'] += 1
        else:
            summary['skipped'] += 1
    return summary


async def run_bp1() -> dict[str, Any]:
    """Один самостоятельный прогон конвейера BP-1: сбор -> raw_item.

    Открывает свою сессию и Redis-клиент, сначала в этой же сессии
    досоздаёт покрытие активных пар «конкурент × источник», затем обходит
    все активные задачи через AdaptiveRunner.run_all. Коммитит оба шага
    вместе и закрывает Redis в finally. Возвращает сводку прогона, включая
    число автоматически созданных задач.
    """
    redis_client = await redis_client_instance.get_client()
    try:
        async with AsyncSessionLocal() as session:
            search_tasks_created = await sync_search_task_coverage(session)
            runner = AdaptiveRunner(
                mode=settings.bp1_adaptive_mode,
                headless=settings.bp1_headless,
                timeout=settings.bp1_parse_timeout_ms,
                max_concurrent=settings.bp1_max_concurrent_tasks,
            )
            results = await runner.run_all(session, redis_client)
            await session.commit()
    finally:
        await redis_client_instance.close()

    summary = _summarize(results)
    summary['search_tasks_created'] = search_tasks_created
    return summary
