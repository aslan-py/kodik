"""
AdaptiveRunner — единая точка входа для адаптивного сбора данных.

Режимы:
- 'adaptive': только адаптивный парсинг
- 'hybrid': адаптивный + legacy fallback
- 'fallback': adaptive → legacy → browser → wayback → HITL
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from src.bp1.tasks import (
    calculate_content_hash,
    get_search_task_config,
    save_raw_item,
    update_timestamp,
)

from .bridge import AdaptiveBridgeParser
from .cache import UnifiedCache
from .classifier import SourceClassifier
from .quality import DataQualityGate

logger = logging.getLogger(__name__)


class AdaptiveRunner:
    """
    Единая точка входа для адаптивного сбора данных.

    Выполняет полный цикл: получение задачи, классификация источника,
    адаптивный парсинг, валидация качества, сохранение в RawItem,
    сохранение HTML + JSON на диск, обновление Redis (дедупликация).
    """

    def __init__(
        self,
        mode: str = 'adaptive',
        headless: bool = True,
        timeout: int = 60000,
        quality_gate_enabled: bool = True,
        cache_profiles: bool = True,
    ):
        self.mode = mode
        self.headless = headless
        self.timeout = timeout
        self.quality_gate_enabled = quality_gate_enabled
        self.cache_profiles = cache_profiles

        self._parser = AdaptiveBridgeParser(headless=headless, timeout=timeout)
        self._quality_gate = DataQualityGate()
        self._cache = UnifiedCache()
        self._classifier = SourceClassifier()
        self._logger = logging.getLogger(__name__)

    def _bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к кэшу для хранения классификаций."""
        if self._cache.redis is None:
            self._cache.redis = redis_client

    def _get_parser_for_source(self, source_name: str):
        """Вернуть специализированный RPA-парсер для источника.

        Для источников с готовым адаптером (fedresurs.ru и др.) возвращает
        парсер из ParserFactory, который применяет полноценный RPA-сценарий
        (обход QRATOR, поиск по ИНН, открытие карточки компании). Для
        остальных источников возвращает None — используется универсальный
        AdaptiveBridgeParser.
        """
        try:
            from src.bp1.parsers import ParserFactory

            # Парсеры зарегистрированы по URL-префиксам (например,
            # 'https://fedresurs.ru/'), поэтому ищем по домену источника.
            registered = ParserFactory.list_sources()
            key = None
            for candidate in registered:
                if candidate == 'adaptive':
                    continue
                if source_name in candidate or candidate in source_name:
                    key = candidate
                    break
            if key is None:
                return None

            parser = ParserFactory.get_parser(
                key,
                **{
                    'headless': self.headless,
                    'timeout': self.timeout,
                },
            )
            # Не используем универсальный адаптивный парсер как
            # специализированный — он уже является fallback по умолчанию.
            if parser.get_parser_type() == 'adaptive':
                return None
            return parser
        except Exception as e:
            self._logger.warning(
                'Не удалось получить специализированный парсер для %s: %s',
                source_name,
                e,
            )
            return None

    async def run_task(
        self,
        task_id: int,
        session: AsyncSession,
        redis_client: Any,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Выполняет одну задачу адаптивного сбора.

        Поток:
        1. Получить SearchTask из БД
        2. Классифицировать источник
        3. Выполнить адаптивный парсинг (с fallback)
        4. Валидировать качество
        5. Сохранить в RawItem (PostgreSQL JSONB)
        6. Сохранить HTML + JSON на диск
        7. Обновить Redis (дедупликация)
        8. Вернуть результат
        """
        # 1. Получаем конфигурацию задачи.
        config = await get_search_task_config(task_id, session)

        if not config['is_active']:
            return {'status': 'skipped', 'reason': 'inactive'}

        source_name = config['source']
        competitor = config['competitor']
        trigger = config['trigger']
        competitor_inn = config['competitor_inn']

        # 2. Классифицируем источник (с кэшированием в Redis).
        self._bind_redis(redis_client)
        self._parser.bind_redis(redis_client)
        classification = await self._cache.get_classification(source_name)
        if classification is None:
            classification = await self._classifier.classify(
                source_name=source_name,
                source_url=source_name,
            )
            await self._cache.set_classification(source_name, classification)
        else:
            self._logger.info(
                'Классификация источника %s взята из кэша (стратегия=%s)',
                source_name,
                classification.recommended_strategy,
            )

        # 3. Формируем URL и параметры.
        search_param = competitor_inn or trigger or competitor
        url = f'https://{source_name}/search?q={search_param}'
        source_request_url = url

        parse_kwargs = {
            'search_task_id': task_id,
            'competitor': competitor,
            'trigger': trigger,
            'source_request_url': source_request_url,
        }

        # 4. Выполняем парсинг.
        #    Для источников с готовым RPA-адаптером (fedresurs.ru и др.)
        #    используем специализированный парсер из ParserFactory, который
        #    применяет полноценный RPA-сценарий (обход QRATOR, поиск по ИНН,
        #    открытие карточки компании). Иначе — универсальный адаптивный.
        try:
            parser = self._get_parser_for_source(source_name)
            if parser is not None:
                # Специализированный RPA-адаптер (fedresurs.ru и др.).
                # Такой парсер ожидает базовый URL источника, а не URL
                # поиска (например, FedresursAdapter принимает
                # 'https://fedresurs.ru').
                parser_url = f'https://{source_name}'
                if competitor_inn:
                    parse_kwargs['inn'] = competitor_inn
                    parse_kwargs['name'] = competitor
                elif trigger and trigger.isdigit() and len(trigger) in (10, 12):
                    parse_kwargs['inn'] = trigger
                    parse_kwargs['name'] = competitor
                else:
                    parse_kwargs['name'] = trigger or competitor
                response = await parser.parse(parser_url, **parse_kwargs)
            else:
                # Универсальный адаптивный парсер.
                response = await self._parser.parse(url, **parse_kwargs)
        except Exception as e:
            self._logger.error(
                'Ошибка адаптивного парсинга (task_id=%s, source=%s): %s',
                task_id,
                source_name,
                e,
            )
            raw_item_id = await save_raw_item(
                session=session,
                search_task_id=task_id,
                data={},
                content_hash='',
                status='error',
                source_request_url=source_request_url,
                error_message=str(e),
            )
            return {
                'status': 'error',
                'search_task_id': task_id,
                'raw_item_id': raw_item_id,
                'error': str(e),
            }

        # 5. Сериализуем и вычисляем хэш.
        data_dict = response.model_dump()
        for item in data_dict.get('items', []):
            item.get('extra', {}).pop('file_path', None)

        content_hash = calculate_content_hash(data_dict)

        # 6. Сверяем через Redis.
        redis_key = str(task_id)
        old_hash = await redis_client.get(redis_key)

        if old_hash == content_hash:
            await update_timestamp(session, task_id)
            return {
                'status': 'unchanged',
                'search_task_id': task_id,
                'hash': content_hash,
            }

        status = 'new' if old_hash is None else 'changed'

        # 7. Сохраняем HTML + JSON на диск.
        html_file_path = None
        if response.items and response.items[0].extra.get('file_path'):
            parser_file_path = response.items[0].extra['file_path']
            if parser_file_path and os.path.exists(parser_file_path):
                html_filename = os.path.basename(parser_file_path)
                html_file_path = os.path.join(
                    settings.bp1_html_dir, html_filename
                )
                import shutil

                shutil.copy2(parser_file_path, html_file_path)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        raw_filename = f'raw_{task_id}_{ts}.json'
        raw_file_path = os.path.join(settings.bp1_raw_dir, raw_filename)
        Path(settings.bp1_raw_dir).mkdir(parents=True, exist_ok=True)
        with open(raw_file_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2, default=str)

        # 8. Сохраняем в БД.
        raw_item_id = await save_raw_item(
            session=session,
            search_task_id=task_id,
            data=data_dict,
            content_hash=content_hash,
            status=status,
            html_file_path=html_file_path,
            source_request_url=source_request_url,
        )

        # 9. Обновляем Redis.
        await redis_client.set(redis_key, content_hash)

        return {
            'status': 'saved',
            'search_task_id': task_id,
            'raw_item_id': raw_item_id,
            'hash': content_hash,
            'status_type': status,
            'html_file_path': html_file_path,
            'raw_file_path': raw_file_path,
            'strategy': classification.recommended_strategy,
        }

    async def run_all(
        self,
        session: AsyncSession,
        redis_client: Any,
        task_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Запустить все активные задачи."""
        from sqlalchemy import select

        from src.bp1.models import SearchTask

        if task_ids:
            stmt = select(SearchTask).where(SearchTask.id.in_(task_ids))
        else:
            stmt = select(SearchTask).where(SearchTask.is_active.is_(True))

        result = await session.execute(stmt)
        tasks = result.scalars().all()

        results: list[dict[str, Any]] = []
        for task in tasks:
            results.append(await self.run_task(task.id, session, redis_client))
        return results
