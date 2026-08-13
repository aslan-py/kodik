"""
Задачи BP-1 для сбора данных из источников.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.bp1.base_parser import BaseParser, ParsedResponse, ParserFactory
from src.bp1.models import SearchTask as ST
from src.bp1.storage import RawDataService, ensure_directories

logger = logging.getLogger(__name__)

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================


async def get_search_task_config(
    search_task_id: int,
    session: AsyncSession,
) -> dict[str, Any]:
    """Получить конфигурацию задачи из БД."""
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
        'source_is_active': task.source.is_active,
        'competitor_is_active': task.competitor.is_active,
    }


def get_parser_for_source(source_name: str, **kwargs) -> BaseParser:
    """Получить парсер по имени источника."""
    return ParserFactory.get_parser(source_name, **kwargs)


def _build_parse_kwargs(
    config: dict[str, Any], search_task_id: int
) -> tuple[str, str, dict]:
    """Сформировать URL поиска и kwargs для parse() по конфигурации задачи.

    Источник поиска — это URI из конфигурации (``config['source']``):
    он может быть полным URL (``https://fedresurs.ru``) либо именем
    источника (``fedresurs.ru``). Для RPA-парсеров, ожидающих базовый
    URL, приводим его к схеме ``https://``.

    Возвращает кортеж ``(parser_url, source_request_url, parse_kwargs)``.
    """
    source = config['source']
    competitor = config['competitor']
    competitor_inn = config['competitor_inn']
    trigger = config['trigger']

    search_param = competitor_inn or trigger or competitor
    base_url = source if source.startswith('http') else f'https://{source}'

    # URL запроса (для meta). Для RPA-источников с поиском формируем
    # поисковую ссылку, иначе — базовый URL источника.
    has_inn = bool(competitor_inn) or (
        bool(trigger) and trigger.isdigit() and len(trigger) in (10, 12)
    )
    if has_inn:
        source_request_url = f'{base_url}/entities?searchString={search_param}'
    else:
        source_request_url = base_url

    parse_kwargs: dict[str, Any] = {
        'search_task_id': search_task_id,
        'competitor': competitor,
        'trigger': trigger,
        'source_request_url': source_request_url,
    }

    # Для RPA-парсеров (fedresurs) в приоритете ИНН компании из БД.
    if competitor_inn:
        parse_kwargs['inn'] = competitor_inn
        parse_kwargs['name'] = competitor
    elif trigger and trigger.isdigit() and len(trigger) in (10, 12):
        parse_kwargs['inn'] = trigger
        parse_kwargs['name'] = competitor
    else:
        parse_kwargs['name'] = trigger or competitor

    return base_url, source_request_url, parse_kwargs


# ============================================================================
# ОСНОВНАЯ ЗАДАЧА
# ============================================================================


async def run_parser_async(
    search_task_id: int, session: AsyncSession, redis_client, **parser_kwargs
) -> dict[str, Any]:
    """Асинхронная версия задачи парсинга."""
    # Создаём директории для хранения данных.
    ensure_directories()

    logger.info('Starting parser for search_task_id=%s', search_task_id)

    service = RawDataService(session, redis_client)

    try:
        # 1. Получаем конфигурацию.
        config = await get_search_task_config(search_task_id, session)

        if not config['is_active']:
            logger.info('Task %s is inactive, skipping', search_task_id)
            return {'status': 'skipped', 'reason': 'inactive'}

        source_name = config['source']
        logger.info(
            'Config: source=%s, competitor=%s, inn=%s, trigger=%s',
            source_name,
            config['competitor'],
            config['competitor_inn'],
            config['trigger'],
        )

        # 2. Создаём парсер.
        parser = get_parser_for_source(source_name, **parser_kwargs)

        # 3. Формируем URL и параметры.
        base_url, source_request_url, parse_kwargs = _build_parse_kwargs(
            config, search_task_id
        )

        # 4. Выполняем парсинг.
        response: ParsedResponse = await parser.parse(base_url, **parse_kwargs)

        # 5. Сериализуем результат.
        data_dict = response.model_dump()

        # 6. Сохраняем результат (хэширование, дедупликация, файлы, RawItem).
        html_source_path = None
        if response.items and response.items[0].extra.get('file_path'):
            html_source_path = response.items[0].extra['file_path']

        result = await service.persist(
            search_task_id=search_task_id,
            response_data=data_dict,
            source_request_url=source_request_url,
            html_source_path=html_source_path,
        )

        return result

    except Exception as e:
        logger.error(
            'Parser failed for task %s: %s', search_task_id, e, exc_info=True
        )

        # Сохраняем ошибку в БД.
        raw_item_id = await service.persist_error(
            search_task_id=search_task_id,
            error_message=str(e),
        )

        return {
            'status': 'error',
            'search_task_id': search_task_id,
            'raw_item_id': raw_item_id,
            'error': str(e),
        }
