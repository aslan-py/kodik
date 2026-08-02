#!/usr/bin/env python
"""
Тестовый скрипт для проверки BP-1 с реальной БД и Redis.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from core.config import settings
from core.database import AsyncSessionLocal
from core.redis_client import redis_client as redis_client_instance
from src.bp1 import run_parser_async
from src.bp1.models import SearchTask

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ============================================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ (для всех модулей проекта)
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger('src.bp1.test_parser')

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

SEPARATOR_LENGTH: int = 80
JSON_PRETTY_MAX_LENGTH: int = 2000
JSON_PRETTY_DB_MAX_LENGTH: int = 3000
HASH_DISPLAY_LENGTH: int = 32
HASH_SHORT_LENGTH: int = 16
PARSER_TIMEOUT: int = 60000
HEADLESS_MODE: bool = True


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================


def log_separator(char: str = '=', length: int = SEPARATOR_LENGTH):
    """Вывести разделитель в лог."""
    logger.info(char * length)


def log_json_pretty(
    data,
    label: str = '',
    max_length: int = JSON_PRETTY_MAX_LENGTH,
):
    """Вывести JSON в лог с ограничением для больших данных."""
    json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if len(json_str) > max_length:
        logger.info(
            '%s (показано %d символов из %d)',
            label,
            max_length,
            len(json_str),
        )
        logger.info('─' * SEPARATOR_LENGTH)
        logger.info(json_str[:max_length])
        logger.info('... (остаток %d символов)', len(json_str) - max_length)
        logger.info('─' * SEPARATOR_LENGTH)
    else:
        logger.info('%s', label)
        logger.info('─' * SEPARATOR_LENGTH)
        logger.info(json_str)
        logger.info('─' * SEPARATOR_LENGTH)


def log_config():
    """Вывести конфигурацию в лог."""
    log_separator('=')
    logger.info('КОНФИГУРАЦИЯ')
    log_separator('=')
    db_url = settings.database_url.replace(settings.postgres_password, '***')
    redis_url = settings.redis_url.replace(settings.redis_password or '', '***')
    logger.info('  Database: %s', db_url)
    logger.info('  Redis: %s', redis_url)
    logger.info('  HTML dir: %s', settings.bp1_html_dir)
    logger.info('  Raw dir: %s', settings.bp1_raw_dir)
    log_separator('=')


async def find_all_active_tasks(session) -> list[int]:
    """Найти все активные задачи в БД."""
    stmt = (
        select(SearchTask)
        .where(SearchTask.is_active.is_(True))
        .order_by(SearchTask.id)
    )
    result = await session.execute(stmt)
    tasks = result.scalars().all()
    return [task.id for task in tasks]


# ============================================================================
# ВЫВОД РЕЗУЛЬТАТОВ
# ============================================================================


async def log_task_result(result: dict, redis, search_task_id: int):
    """Вывести результат выполнения одной задачи в лог."""
    log_separator('=')
    logger.info('РЕЗУЛЬТАТ (задача %d)', search_task_id)
    log_separator('=')

    logger.info('  Статус: %s', result.get('status'))
    logger.info('  Search Task ID: %s', result.get('search_task_id'))
    logger.info('  Raw Item ID: %s', result.get('raw_item_id'))
    logger.info('  Хэш: %s', result.get('hash', ''))
    logger.info('  Тип: %s', result.get('status_type'))

    if result.get('html_file_path'):
        logger.info('  HTML файл: %s', result.get('html_file_path'))
    if result.get('raw_file_path'):
        logger.info('  Raw файл: %s', result.get('raw_file_path'))
    if result.get('error'):
        logger.warning('  Ошибка: %s', result.get('error'))

    # Проверяем, что данные реально сохранились в БД
    if result.get('status') == 'saved':
        async with AsyncSessionLocal() as session:
            from src.bp1.models import RawItem

            stmt = select(RawItem).where(
                RawItem.id == result.get('raw_item_id')
            )
            db_result = await session.execute(stmt)
            db_item = db_result.scalar_one_or_none()

            if db_item:
                logger.info('Данные найдены в БД (RawItem id=%d)', db_item.id)
                logger.info('  Статус: %s', db_item.status)
                h = db_item.content_hash
                logger.info(
                    '  Хэш: %s...', h[:HASH_DISPLAY_LENGTH] if h else 'None'
                )
                logger.info('  HTML: %s', db_item.html_file_path)
                logger.info('  URL запроса: %s', db_item.source_request_url)

                if db_item.raw_data:
                    log_json_pretty(
                        db_item.raw_data,
                        'RAW_DATA из БД',
                        max_length=JSON_PRETTY_DB_MAX_LENGTH,
                    )
            else:
                rid = result.get('raw_item_id')
                logger.warning('Данные не найдены в БД (ID=%s)', rid)

    # Проверяем Redis
    logger.info('REDIS (ключ: %d)', search_task_id)
    logger.info('─' * SEPARATOR_LENGTH)
    redis_key = str(search_task_id)
    stored_hash = await redis.get(redis_key)
    if stored_hash:
        logger.info('  Значение: %s', stored_hash)
    else:
        logger.info('  Ключ не найден')


# ============================================================================
# ОСНОВНОЙ ТЕСТ
# ============================================================================


async def test_with_real_db():
    """Тест с реальной БД и Redis."""

    log_separator('=')
    logger.info('ТЕСТ BP-1: РЕАЛЬНАЯ БД И REDIS')
    log_separator('=')

    # Показываем конфигурацию
    log_config()

    # Ищем все активные задачи
    async with AsyncSessionLocal() as session:
        search_task_ids = await find_all_active_tasks(session)

    if not search_task_ids:
        logger.warning('В БД нет активных задач search_task.')
        logger.warning('Запустите: python -m core.scripts.seed_all')
        logger.warning('Или:     python -m core.scripts.stages.dictionaries')
        logger.warning('И затем: python -m core.scripts.stages.bp1')
        return

    logger.info('Найдено активных задач: %d', len(search_task_ids))
    logger.info('ID задач: %s', search_task_ids)

    # Получаем Redis клиент (один на все задачи)
    redis = await redis_client_instance.get_client()

    total_start = datetime.now()
    task_results = []

    for idx, search_task_id in enumerate(search_task_ids, 1):
        log_separator('=')
        logger.info(
            'ЗАДАЧА %d/%d: ID=%d', idx, len(search_task_ids), search_task_id
        )
        log_separator('=')

        logger.info('ЗАПУСК ПАРСИНГА...')
        logger.info('─' * SEPARATOR_LENGTH)

        task_start = datetime.now()

        try:
            # Создаем сессию БД (новая сессия на каждую задачу)
            async with AsyncSessionLocal() as session:
                result = await run_parser_async(
                    search_task_id=search_task_id,
                    session=session,
                    redis_client=redis,
                    headless=HEADLESS_MODE,
                    timeout=PARSER_TIMEOUT,
                )

            task_elapsed = (datetime.now() - task_start).total_seconds()
            logger.info('Время выполнения: %.2f секунд', task_elapsed)

            await log_task_result(result, redis, search_task_id)
            task_results.append(result)

        except Exception as e:
            logger.error(
                'ОШИБКА при выполнении задачи %d: %s', search_task_id, e
            )
            import traceback

            traceback.print_exc()
            task_results.append(
                {
                    'status': 'error',
                    'search_task_id': search_task_id,
                    'error': str(e),
                }
            )

        log_separator('=')

    # Закрываем Redis
    await redis_client_instance.close()

    total_elapsed = (datetime.now() - total_start).total_seconds()

    # Итоговая сводка
    log_separator('=')
    logger.info('ИТОГОВАЯ СВОДКА')
    log_separator('=')
    logger.info('  Всего задач: %d', len(search_task_ids))
    logger.info('  Общее время: %.2f секунд', total_elapsed)
    for r in task_results:
        tid = r.get('search_task_id', '?')
        st = r.get('status', '?')
        h = r.get('hash', '')[:HASH_SHORT_LENGTH] if r.get('hash') else ''
        logger.info('  Задача %s: статус=%s, хэш=%s', tid, st, h)
    log_separator('=')
    logger.info('ТЕСТ ЗАВЕРШЕН')
    log_separator('=')


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║              ТЕСТ BP-1: РЕАЛЬНАЯ БД И REDIS                              ║
║                                                                          ║
║   Тест использует:                                                       ║
║   - Реальную PostgreSQL (из core/config.py)                              ║
║   - Реальный Redis (из core/config.py)                                   ║
║   - Сохранение HTML в src/bp1/data/html_pages/                           ║
║   - Сохранение JSON в src/bp1/data/raw/                                  ║
║                                                                          ║
║   ВНИМАНИЕ:                                                              ║
║   - В БД должна быть хотя бы одна активная search_task                   ║
║   - Должны быть заполнены competitor, source, trigger                    ║
║   - Для fedresurs используется ИНН из Competitor.inn                     ║
╚══════════════════════════════════════════════════════════════════════════╝
""")

    confirm = input('Продолжить? (y/n): ').strip().lower()
    if confirm == 'y':
        asyncio.run(test_with_real_db())
    else:
        print('Тест отменен')
