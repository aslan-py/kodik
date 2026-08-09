"""
AdaptiveRunner — единая точка входа для адаптивного сбора данных.

Режимы:
- 'adaptive': только адаптивный парсинг
- 'hybrid': адаптивный + legacy fallback
- 'fallback': adaptive → legacy → browser → wayback → HITL
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from src.bp1.models import Source
from src.bp1.storage import RawDataService
from src.bp1.tasks import get_search_task_config

from ..core.cache import UnifiedCache
from ..core.quality import DataQualityGate
from ..schemas import PipelineReport, PipelineStage, UnifiedConfig
from ..strategies.classifier import SourceClassifier
from .bridge import AdaptiveBridgeParser
from .sources import build_search_url, extract_host

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
        max_concurrent: int = 5,
    ):
        self.mode = mode
        self.headless = headless
        self.timeout = timeout
        self.quality_gate_enabled = quality_gate_enabled
        self.cache_profiles = cache_profiles
        self.max_concurrent = max_concurrent

        # Единая конфигурация пайплайна (UnifiedConfig).
        self.config = UnifiedConfig(
            mode=mode,
            headless=headless,
            timeout=timeout,
            quality_gate_enabled=quality_gate_enabled,
            cache_profiles=cache_profiles,
            max_concurrent=max_concurrent,
        )

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
        # Отчёт пайплайна (PipelineReport) для отслеживания стадий.
        report_start = time.monotonic()
        pipeline_id = uuid.uuid4().hex
        report = PipelineReport(
            pipeline_id=pipeline_id,
            mode=self.mode,
        )
        stages: list[PipelineStage] = []

        def _add_stage(
            name: str,
            status: str = 'ok',
            detail: dict[str, Any] | None = None,
        ) -> None:
            stages.append(
                PipelineStage(
                    name=name,
                    status=status,
                    detail=detail or {},
                )
            )

        # 1. Получаем конфигурацию задачи.
        config = await get_search_task_config(task_id, session)

        if not config['is_active']:
            return {'status': 'skipped', 'reason': 'inactive'}

        source_name = config['source']
        competitor = config['competitor']
        trigger = config['trigger']
        competitor_inn = config['competitor_inn']

        # Адаптивный парсинг ведётся только по активным source и competitor.
        # Флаг is_active у SearchTask может быть True, но если сам источник
        # или конкурент выключены (is_active=False), задачу пропускаем.
        if not config.get('source_is_active', True):
            return {
                'status': 'skipped',
                'reason': 'source_inactive',
                'search_task_id': task_id,
            }
        if not config.get('competitor_is_active', True):
            return {
                'status': 'skipped',
                'reason': 'competitor_inactive',
                'search_task_id': task_id,
            }

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
        _add_stage(
            'classify',
            detail={'strategy': classification.recommended_strategy},
        )

        # 3. Формируем URL и параметры.
        search_param = competitor_inn or trigger or competitor
        url = build_search_url(source_name, search_param)
        source_request_url = url

        # 3.1. Circuit breaker: если источник временно заблокирован в Redis
        #     (все стратегии падали недавно), пропускаем задачу, не тратя
        #     ресурсы на парсинг.
        if await self._cache.is_source_blocked(source_name):
            self._logger.info(
                'Источник %s временно заблокирован (circuit breaker), '
                'задача %s пропущена',
                source_name,
                task_id,
            )
            return {
                'status': 'source_unavailable',
                'search_task_id': task_id,
                'source': source_name,
                'reason': 'circuit_open',
            }

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
                parser_url = f'https://{extract_host(source_name)}'
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
                # Универсальный адаптивный парсер. Передаём реальное имя
                # источника (hostname), чтобы адаптер/классификация/профиль
                # кэшировались именно под этим источником, а не под общим
                # именем 'adaptive'.
                response = await self._parser.parse(
                    url,
                    source_name=source_name,
                    **parse_kwargs,
                )
            _add_stage(
                'parse',
                detail={
                    'items': len(response.items),
                    'strategy': getattr(response, 'strategy_used', None),
                },
            )
            # Источник успешно спарсен — снимаем временную блокировку и
            # сбрасываем счётчик подряд идущих отказов.
            await self._cache.unblock_source(source_name)
            await self._cache.reset_fail_count(source_name)
        except Exception as e:
            self._logger.error(
                'Ошибка адаптивного парсинга (task_id=%s, source=%s): %s',
                task_id,
                source_name,
                e,
            )
            await self._record_source_failure(source_name, session)
            service = RawDataService(session, redis_client)
            raw_item_id = await service.persist_error(
                search_task_id=task_id,
                error_message=str(e),
                source_request_url=source_request_url,
            )
            return {
                'status': 'error',
                'search_task_id': task_id,
                'raw_item_id': raw_item_id,
                'error': str(e),
            }

        # 5. Сохраняем результат через общий сервис персистентности
        #    (хэширование, дедупликация по Redis, HTML/JSON на диск, RawItem).
        service = RawDataService(session, redis_client)
        data_dict = response.model_dump()
        html_source_path = None
        if response.items and response.items[0].extra.get('file_path'):
            html_source_path = response.items[0].extra['file_path']

        persisted = await service.persist(
            search_task_id=task_id,
            response_data=data_dict,
            source_request_url=source_request_url,
            html_source_path=html_source_path,
        )

        # 6. Финализируем отчёт пайплайна.
        _add_stage(
            'save',
            detail={
                'raw_item_id': persisted.get('raw_item_id'),
                'status_type': persisted.get('status_type'),
                'hash': persisted.get('hash'),
            },
        )
        report.stages = stages
        report.finished_at = datetime.now()
        report.total_duration_ms = int((time.monotonic() - report_start) * 1000)
        report.overall_status = 'ok'

        persisted['strategy'] = classification.recommended_strategy
        persisted['pipeline_report'] = report.model_dump(mode='json')
        return persisted

    async def _record_source_failure(
        self,
        source_name: str,
        session: AsyncSession,
    ) -> None:
        """Зафиксировать полный отказ источника (all strategies failed).

        Двухуровневая логика (фича 1+2 circuit breaker):

        1. Блокируем источник в Redis на TTL circuit breaker (временная
           блокировка, чтобы не тратить ресурсы на повторные попытки).
        2. Инкрементируем счётчик подряд идущих отказов. Если он достиг
           ``settings.source_disable_threshold`` — отключаем ``Source``
           в БД (``is_active=False``) и сбрасываем счётчик.
        """
        ttl = settings.source_circuit_ttl_seconds
        threshold = settings.source_disable_threshold

        await self._cache.block_source(source_name, ttl=ttl)

        fail_count = await self._cache.increment_fail_count(source_name)
        self._logger.warning(
            'Источник %s недоступен, попытка отказа %d/%d (blocked %ss)',
            source_name,
            fail_count,
            threshold,
            ttl,
        )

        if fail_count >= threshold:
            stmt = select(Source).where(Source.name == source_name)
            source = (await session.execute(stmt)).scalar_one_or_none()
            if source is not None and source.is_active:
                source.is_active = False
                await session.commit()
                self._logger.warning(
                    'Источник %s отключён в БД (is_active=False) после '
                    '%d подряд отказов',
                    source_name,
                    fail_count,
                )
            await self._cache.reset_fail_count(source_name)

    async def run_all(
        self,
        session: AsyncSession,
        redis_client: Any,
        task_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Запустить все активные задачи.

        Учитываются флаги активности трёх уровней: сама SearchTask, её
        Source и Competitor. Если любой из них выключен (is_active=False),
        задача пропускается — адаптивный поиск ведётся только по активным
        источникам и конкурентам.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from src.bp1.models import SearchTask

        if task_ids:
            stmt = (
                select(SearchTask)
                .where(SearchTask.id.in_(task_ids))
                .options(
                    selectinload(SearchTask.source),
                    selectinload(SearchTask.competitor),
                )
            )
        else:
            stmt = (
                select(SearchTask)
                .where(SearchTask.is_active.is_(True))
                .options(
                    selectinload(SearchTask.source),
                    selectinload(SearchTask.competitor),
                )
            )

        result = await session.execute(stmt)
        tasks = result.scalars().all()

        results: list[dict[str, Any]] = []
        for task in tasks:
            if not task.source.is_active or not task.competitor.is_active:
                results.append(
                    {
                        'status': 'skipped',
                        'search_task_id': task.id,
                        'reason': (
                            'source_inactive'
                            if not task.source.is_active
                            else 'competitor_inactive'
                        ),
                    }
                )
                continue
            results.append(await self.run_task(task.id, session, redis_client))
        return results

    async def run_source_competitor(
        self,
        source: str,
        competitor: str,
        session: AsyncSession,
        redis_client: Any,
    ) -> dict[str, Any]:
        """Выполнить сбор для конкретной пары источник + конкурент.

        В отличие от run_all (который берёт все активные задачи из БД),
        этот метод строит отдельный запрос к БД по конкретному источнику
        и конкуренту:
        1. Находит или создаёт Source (по нормализованному имени).
        2. Находит или создаёт Competitor.
        3. Находит или создаёт SearchTask (связку без триггера).
        4. Запускает run_task для этой задачи.
        """
        from src.bp1.models import Competitor, SearchTask, Source

        from .sources import SourceRegistrationService, normalize_source_url

        self._bind_redis(redis_client)

        # 1. Источник: ищем по нормализованному имени, иначе регистрируем.
        source_name = normalize_source_url(source)
        src_stmt = select(Source).where(Source.name == source_name)
        src = (await session.execute(src_stmt)).scalar_one_or_none()
        if src is None:
            reg = await SourceRegistrationService(
                session, redis_client=redis_client
            ).register(source)
            src_id = reg.source_id
            self._logger.info(
                'Источник %s зарегистрирован (source_id=%s)',
                source_name,
                src_id,
            )
        else:
            src_id = src.id
            # Адаптивный поиск ведётся только по активным источникам.
            if not src.is_active:
                return {
                    'status': 'skipped',
                    'reason': 'source_inactive',
                    'source': source_name,
                }

        # 2. Конкурент: ищем по имени, иначе создаём.
        comp_stmt = select(Competitor).where(Competitor.name == competitor)
        comp = (await session.execute(comp_stmt)).scalar_one_or_none()
        if comp is None:
            comp = Competitor(name=competitor)
            session.add(comp)
            await session.flush()
            self._logger.info(
                'Конкурент %s создан (id=%s)', competitor, comp.id
            )
        else:
            # Адаптивный поиск ведётся только по активным конкурентам.
            if not comp.is_active:
                return {
                    'status': 'skipped',
                    'reason': 'competitor_inactive',
                    'competitor': competitor,
                }

        # 3. SearchTask: ищем существующую связку без триггера, иначе создаём.
        task_stmt = select(SearchTask).where(
            SearchTask.source_id == src_id,
            SearchTask.competitor_id == comp.id,
            SearchTask.trigger_id.is_(None),
        )
        task = (await session.execute(task_stmt)).scalar_one_or_none()
        if task is None:
            task = SearchTask(
                source_id=src_id,
                competitor_id=comp.id,
                trigger_id=None,
                is_active=True,
            )
            session.add(task)
            await session.flush()
            self._logger.info(
                'Задача создана (search_task_id=%s) для source=%s',
                task.id,
                source_name,
            )
        await session.commit()

        # 4. Запускаем сбор.
        return await self.run_task(task.id, session, redis_client)
