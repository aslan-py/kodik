"""
Задачи BP-1 для сбора данных из источников.
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from src.bp1.base_parser import BaseParser, ParsedResponse, ParserFactory
from src.bp1.models import RawItem

logger = logging.getLogger(__name__)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================


def calculate_content_hash(data: dict[str, Any]) -> str:
    """
    Вычислить хэш от канонического JSON.

    Хэш считается ТОЛЬКО от items (список результатов), так как:
    - meta содержит изменяемые поля (source_request_url, search_task_id и т.д.)
    - items — это смысловое содержимое, которое должно определять изменения

    Из items дополнительно исключаются:
    - extra.file_path — путь к HTML-файлу (меняется при каждом запуске)
    """
    items = data.get('items', [])
    # Очищаем каждый item от file_path в extra
    clean_items = []
    for item in items:
        item_copy = item.copy()
        if 'extra' in item_copy:
            item_copy['extra'] = item_copy['extra'].copy()
            item_copy['extra'].pop('file_path', None)
        clean_items.append(item_copy)

    json_str = json.dumps(clean_items, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()


async def get_search_task_config(
    search_task_id: int,
    session: AsyncSession,
) -> dict[str, Any]:
    """Получить конфигурацию задачи из БД."""
    from sqlalchemy.orm import selectinload

    from src.bp1.models import SearchTask as ST

    stmt = (
        select(ST)
        .where(ST.id == search_task_id)
        .options(
            selectinload(ST.competitor),
            selectinload(ST.source),
            selectinload(ST.trigger),
        )
    )
    result = await session.execute(stmt)
    task = result.scalar_one()

    return {
        'id': task.id,
        'competitor': task.competitor.name,
        'competitor_inn': task.competitor.inn,
        'source': task.source.name,
        'trigger': task.trigger.keyword if task.trigger else None,
        'is_active': task.is_active,
    }


async def save_raw_item(
    session: AsyncSession,
    search_task_id: int,
    data: dict[str, Any],
    content_hash: str,
    status: str,
    html_file_path: str | None = None,
    source_request_url: str | None = None,
    error_message: str | None = None,
) -> int:
    """Сохранить сырые данные в БД."""
    raw_item = RawItem(
        search_task_id=search_task_id,
        status=status,
        content_hash=content_hash,
        raw_data=data,
        html_file_path=html_file_path,
        source_request_url=source_request_url,
        error_message=error_message,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(raw_item)
    await session.commit()
    await session.refresh(raw_item)
    return raw_item.id


async def update_timestamp(session: AsyncSession, search_task_id: int) -> None:
    """Обновить updated_at для последней записи задачи."""
    # 1. Сначала получаем ID последней записи
    select_stmt = (
        select(RawItem.id)
        .where(RawItem.search_task_id == search_task_id)
        .order_by(RawItem.created_at.desc())
        .limit(1)
    )
    result = await session.execute(select_stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return

    # 2. Обновляем updated_at по ID
    stmt = (
        update(RawItem)
        .where(RawItem.id == row)
        .values(updated_at=datetime.utcnow())
    )
    await session.execute(stmt)
    await session.commit()


def get_parser_for_source(source_name: str, **kwargs) -> BaseParser:
    """Получить парсер по имени источника."""
    return ParserFactory.get_parser(source_name, **kwargs)


def ensure_directories():
    """Создать необходимые директории для хранения данных."""
    dirs = [settings.bp1_html_dir, settings.bp1_raw_dir]
    for path in dirs:
        Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================================
# ОСНОВНАЯ ЗАДАЧА
# ============================================================================


async def run_parser_async(
    search_task_id: int, session: AsyncSession, redis_client, **parser_kwargs
) -> dict[str, Any]:
    """
    Асинхронная версия задачи парсинга.
    """
    # Создаем директории
    ensure_directories()

    logger.info(f'Starting parser for search_task_id={search_task_id}')

    try:
        # 1. Получаем конфигурацию
        config = await get_search_task_config(search_task_id, session)

        if not config['is_active']:
            logger.info(f'Task {search_task_id} is inactive, skipping')
            return {'status': 'skipped', 'reason': 'inactive'}

        source_name = config['source']
        competitor_inn = config['competitor_inn']
        trigger = config['trigger']

        logger.info(
            'Config: source=%s, competitor=%s, inn=%s, trigger=%s',
            source_name,
            config['competitor'],
            competitor_inn,
            trigger,
        )

        # 2. Создаем парсер
        parser = get_parser_for_source(source_name, **parser_kwargs)

        # 3. Формируем URL и параметры
        base_url = 'https://fedresurs.ru'

        # Для fedresurs поиск всегда по ИНН компании
        search_param = competitor_inn or trigger or config['competitor']
        url = f'https://fedresurs.ru/entities?searchString={search_param}'
        source_request_url = url

        parse_kwargs = {
            'search_task_id': search_task_id,
            'competitor': config['competitor'],
            'trigger': trigger,
            'source_request_url': source_request_url,
        }

        # Для fedresurs в приоритете ИНН компании из БД
        if competitor_inn:
            parse_kwargs['inn'] = competitor_inn
            parse_kwargs['name'] = config['competitor']
        elif trigger and trigger.isdigit() and len(trigger) in (10, 12):
            parse_kwargs['inn'] = trigger
            parse_kwargs['name'] = config['competitor']
        else:
            parse_kwargs['name'] = trigger or config['competitor']

        # 4. Выполняем парсинг
        response: ParsedResponse = await parser.parse(base_url, **parse_kwargs)

        # 5. Сериализуем в JSON
        data_dict = response.model_dump()

        # 6. Удаляем file_path из extra (меняется при каждом запуске)
        for item in data_dict.get('items', []):
            item.get('extra', {}).pop('file_path', None)

        # 7. Вычисляем хэш (только от items, без meta и file_path)
        content_hash = calculate_content_hash(data_dict)

        # 8. Проверяем хэш через Redis
        redis_key = str(search_task_id)
        old_hash = await redis_client.get(redis_key)

        if old_hash == content_hash:
            # Ничего не изменилось
            logger.info(f'Content unchanged for task {search_task_id}')
            await update_timestamp(session, search_task_id)
            return {
                'status': 'unchanged',
                'search_task_id': search_task_id,
                'hash': content_hash,
            }

        # 9. Определяем статус
        status = 'new' if old_hash is None else 'changed'

        # 10. Сохраняем HTML файл
        html_file_path = None
        if response.items and response.items[0].extra.get('file_path'):
            # Используем путь от парсера, но копируем в нашу директорию
            parser_file_path = response.items[0].extra['file_path']
            if parser_file_path and os.path.exists(parser_file_path):
                # Копируем в нашу папку html_pages
                html_filename = os.path.basename(parser_file_path)
                html_file_path = os.path.join(
                    settings.bp1_html_dir, html_filename
                )

                # Копируем файл
                import shutil

                shutil.copy2(parser_file_path, html_file_path)
                logger.info(f'HTML file copied to: {html_file_path}')

        # 11. Сохраняем raw_data как JSON файл
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        raw_filename = f'raw_{search_task_id}_{ts}.json'
        raw_file_path = os.path.join(settings.bp1_raw_dir, raw_filename)

        with open(raw_file_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f'Raw data saved to: {raw_file_path}')

        # 12. Сохраняем в БД
        raw_item_id = await save_raw_item(
            session=session,
            search_task_id=search_task_id,
            data=data_dict,
            content_hash=content_hash,
            status=status,
            html_file_path=html_file_path,
            source_request_url=source_request_url,
        )

        # 13. Обновляем Redis
        await redis_client.set(redis_key, content_hash)

        logger.info(f'Saved raw_item_id={raw_item_id} with status={status}')

        return {
            'status': 'saved',
            'search_task_id': search_task_id,
            'raw_item_id': raw_item_id,
            'hash': content_hash,
            'status_type': status,
            'html_file_path': html_file_path,
            'raw_file_path': raw_file_path,
        }

    except Exception as e:
        logger.error(
            'Parser failed for task %s: %s',
            search_task_id,
            e,
            exc_info=True,
        )

        # Сохраняем ошибку в БД
        raw_item_id = await save_raw_item(
            session=session,
            search_task_id=search_task_id,
            data={},
            content_hash='',
            status='error',
            error_message=str(e),
        )

        return {
            'status': 'error',
            'search_task_id': search_task_id,
            'raw_item_id': raw_item_id,
            'error': str(e),
        }
