#!/usr/bin/env python3
# src/bp1/cli.py
"""
CLI интерфейс для BP-1.

Использование:
    # Запустить все активные задачи (тестовый режим)
    python -m src.bp1.cli run --mode direct

    # Запустить конкретную задачу
    python -m src.bp1.cli run --task-id 26 --mode direct

    # Запустить несколько задач
    python -m src.bp1.cli run --task-ids 1,2,3 --mode direct

    # Запустить через Celery (production)
    python -m src.bp1.cli run --mode celery

    # Показать активные задачи
    python -m src.bp1.cli list

    # Очистить Redis
    python -m src.bp1.cli clear-redis
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.bp1.constants import (
    CLI_SEPARATOR_WIDTH,
    DEFAULT_TIMEOUT_MS,
    MODE_CELERY,
    MODE_DIRECT,
    SEPARATOR_LINE,
    STATUS_ERROR,
    STATUS_SAVED,
    STATUS_SKIPPED,
    STATUS_UNCHANGED,
)
from src.bp1.runner import run_pipeline_sync

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


def parse_task_ids(task_ids_str: str) -> list[int]:
    """Парсинг строки с ID задач."""
    if not task_ids_str:
        return []
    return [int(x.strip()) for x in task_ids_str.split(',') if x.strip()]


async def list_tasks():
    """Показать все активные задачи."""
    from sqlalchemy import select

    from core.database import AsyncSessionLocal
    from src.bp1.models import SearchTask

    async with AsyncSessionLocal() as session:
        stmt = (
            select(SearchTask)
            .where(SearchTask.is_active.is_(True))
            .order_by(SearchTask.id)
        )
        result = await session.execute(stmt)
        tasks = result.scalars().all()

        print()
        print('Активные задачи:')
        print(SEPARATOR_LINE * CLI_SEPARATOR_WIDTH)
        for task in tasks:
            print(f'  ID: {task.id}')
            print(f'    Конкурент: {task.competitor.name}')
            print(f'    Источник: {task.source.name}')
            trigger_word = task.trigger.keyword if task.trigger else 'None'
            print(f'    Триггер: {trigger_word}')
            print()


async def _clear_task_redis_keys(session, redis) -> tuple[list[str], int]:
    """Удаляет ключи дедупликации BP-1, привязанные к существующим задачам.

    В отличие от прежней реализации (``redis.keys('*')`` + фильтр
    ``k.isdigit()``), не сканирует Redis целиком и не угадывает "наши"
    ключи по формату — ``KEYS *`` блокирует инстанс Redis на время
    полной выборки, а числовой формат ключа (``RawDataService._redis_key``,
    см. ``storage.py``) не отличим от произвольного стороннего числового
    ключа, если тот же Redis делят другие системы. Вместо этого берёт
    список реальных ``SearchTask.id`` из БД и удаляет ровно
    соответствующие им ключи.

    Возвращает ``(candidate_keys, deleted_count)``: список ключей,
    привязанных к существующим задачам, и число фактически удалённых
    (``redis.delete()`` не удаляет то, чего не было — например, для задачи,
    которая ещё ни разу не собиралась успешно).
    """
    from sqlalchemy import select

    from src.bp1.models import SearchTask
    from src.bp1.storage import RawDataService

    service = RawDataService(session=session, redis_client=redis)
    result = await session.execute(select(SearchTask.id))
    task_keys = [service._redis_key(task_id) for (task_id,) in result.all()]

    if not task_keys:
        return [], 0

    deleted = await redis.delete(*task_keys)
    return task_keys, deleted


async def clear_redis():
    """Очистить Redis от ключей дедупликации задач BP-1."""
    from core.database import AsyncSessionLocal
    from core.redis_client import redis_client

    redis = await redis_client.get_client()
    async with AsyncSessionLocal() as session:
        task_keys, deleted = await _clear_task_redis_keys(session, redis)

    print()
    if task_keys:
        print(f'Удалено ключей: {deleted}')
        print(f'Ключи: {task_keys}')
    else:
        print('Нет ключей для удаления')

    await redis_client.close()


def main():
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description='BP-1 Pipeline CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python -m src.bp1.cli run --mode direct
  python -m src.bp1.cli run --task-id 26 --mode direct
  python -m src.bp1.cli run --task-ids 1,2,3 --mode direct
  python -m src.bp1.cli run --mode celery
  python -m src.bp1.cli list
  python -m src.bp1.cli clear-redis
        """,
    )

    subparsers = parser.add_subparsers(dest='command', help='Команда')

    # Команда run
    run_parser = subparsers.add_parser('run', help='Запустить пайплайн')
    run_parser.add_argument(
        '--mode',
        choices=[MODE_DIRECT, MODE_CELERY],
        default=MODE_DIRECT,
        help='Режим запуска: direct (тестовый) или celery (production)',
    )
    run_parser.add_argument(
        '--task-id', type=int, help='Запустить одну задачу по ID'
    )
    run_parser.add_argument(
        '--task-ids',
        type=str,
        help='Запустить несколько задач (через запятую, например: 1,2,3)',
    )
    run_parser.add_argument(
        '--headless',
        action='store_true',
        default=True,
        help='Запускать браузер в headless режиме',
    )
    run_parser.add_argument(
        '--no-headless',
        action='store_false',
        dest='headless',
        help='Запускать браузер с GUI (для отладки)',
    )
    run_parser.add_argument(
        '--timeout',
        type=int,
        default=DEFAULT_TIMEOUT_MS,
        help='Таймаут для парсинга в мс',
    )

    # Команда list
    subparsers.add_parser('list', help='Показать активные задачи')

    # Команда clear-redis
    subparsers.add_parser('clear-redis', help='Очистить Redis')

    args = parser.parse_args()

    if args.command == 'run':
        # Определяем список задач
        task_ids = None
        if args.task_id:
            task_ids = [args.task_id]
        elif args.task_ids:
            task_ids = parse_task_ids(args.task_ids)

        # Запускаем пайплайн
        print()
        print(f'Запуск BP-1 в режиме: {args.mode}')
        print(SEPARATOR_LINE * CLI_SEPARATOR_WIDTH)

        results = run_pipeline_sync(
            mode=args.mode,
            task_ids=task_ids,
            headless=args.headless,
            timeout=args.timeout,
        )

        # Выводим результаты
        print()
        print('Результаты:')
        print(SEPARATOR_LINE * CLI_SEPARATOR_WIDTH)
        for r in results:
            status = r.get('status', '?')
            task_id = r.get('task_id', r.get('search_task_id', '?'))
            print(f'  Задача {task_id}: {status}')

        # Итоговая сводка
        saved = sum(1 for r in results if r.get('status') == STATUS_SAVED)
        unchanged = sum(
            1 for r in results if r.get('status') == STATUS_UNCHANGED
        )
        error = sum(1 for r in results if r.get('status') == STATUS_ERROR)
        skipped = sum(1 for r in results if r.get('status') == STATUS_SKIPPED)

        print()
        print('Сводка:')
        print(f'  Всего: {len(results)}')
        print(f'  Сохранено: {saved}')
        print(f'  Без изменений: {unchanged}')
        print(f'  Ошибок: {error}')
        print(f'  Пропущено: {skipped}')

    elif args.command == 'list':
        asyncio.run(list_tasks())

    elif args.command == 'clear-redis':
        asyncio.run(clear_redis())

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
