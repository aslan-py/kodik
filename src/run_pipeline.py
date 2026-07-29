#!/usr/bin/env python3
"""Production-пайплайн конкурентной разведки.

Оркестрирует сбор данных из нескольких источников (kad_arbitr, fedresurs)
и сохраняет результаты в JSONB-файлы через raw_storage.

Использование:
    python -m src.run_pipeline
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from src.bp1.collectors.fedresurs_rpa import FedresursRPA
from src.bp1.collectors.fedresurs_rpa.models import (
    SearchRequest as FedresursRequest,
)
from src.bp1.collectors.kad_arbitr_rpa import KadArbitrParser
from src.bp1.collectors.kad_arbitr_rpa.models import (
    ParsingRequest as KadRequest,
)
from src.bp1.models import (
    Competitor,
    RawItem,
    RawItemStatus,
    SearchTask,
    Source,
    Trigger,
)
from src.bp1.raw_storage import RawDataRepository
from src.bp1.raw_storage.backends.disk_backend import DiskBackend
from src.bp1.raw_storage.core.models import (
    MetaInfo,
    RawDataFile,
)
from src.bp1.raw_storage.core.models import (
    RawDataItem as StorageItem,
)
from src.bp1.raw_storage.utils.hashing import compute_content_hash

# ── Logging ──────────────────────────────────────────────────────────────────

logger = logging.getLogger('pipeline')


class JSONStructureLogger:
    """Структурированное JSON-логирование событий пайплайна."""

    @staticmethod
    def _log(level: int, event: str, **kwargs: Any) -> None:
        record = {'event': event, 'timestamp': datetime.now(UTC).isoformat()}
        record.update(kwargs)
        logger.log(level, json.dumps(record, ensure_ascii=False))

    @classmethod
    def info(cls, event: str, **kwargs: Any) -> None:
        cls._log(logging.INFO, event, **kwargs)

    @classmethod
    def warning(cls, event: str, **kwargs: Any) -> None:
        cls._log(logging.WARNING, event, **kwargs)

    @classmethod
    def error(cls, event: str, **kwargs: Any) -> None:
        cls._log(logging.ERROR, event, **kwargs)


# ── SourceManager ────────────────────────────────────────────────────────────


@dataclass
class SourceState:
    """Внутреннее состояние одного источника."""

    error_count: int = 0
    max_errors: int = 3
    disabled: bool = False


class SourceManager:
    """Реестр парсеров с отслеживанием ошибок и авто-отключением.

    Отслеживает последовательные ошибки по каждому источнику.
    После max_errors (по умолчанию 3) последовательных сбоев
    источник автоматически отключается до конца прогона пайплайна.
    """

    def __init__(self, max_errors: int = 3) -> None:
        self._sources: dict[str, SourceState] = {}
        self.max_errors = max_errors

    def register(self, name: str) -> None:
        """Зарегистрировать источник для отслеживания."""
        if name not in self._sources:
            self._sources[name] = SourceState(max_errors=self.max_errors)

    def increment_error(self, name: str) -> bool:
        """Увеличить счётчик ошибок для источника.

        Returns:
            True, если источник только что был отключён
            (превышен порог max_errors).
        """
        state = self._sources.get(name)
        if state is None:
            return False
        state.error_count += 1
        if state.error_count >= state.max_errors and not state.disabled:
            state.disabled = True
            JSONStructureLogger.warning(
                'source_disabled',
                source_name=name,
                error_count=state.error_count,
                max_errors=state.max_errors,
            )
            return True
        return False

    def reset_errors(self, name: str) -> None:
        """Сбросить счётчик ошибок после успешного парсинга."""
        state = self._sources.get(name)
        if state is not None:
            state.error_count = 0

    def is_enabled(self, name: str) -> bool:
        """Проверить, активен ли ещё источник."""
        state = self._sources.get(name)
        if state is None:
            return True
        return not state.disabled

    @property
    def disabled_sources(self) -> list[str]:
        """Вернуть список имён источников, которые были отключены."""
        return [name for name, state in self._sources.items() if state.disabled]


# ── ParserFactory ────────────────────────────────────────────────────────────


class ParserFactory:
    """Фабрика для создания экземпляров парсеров по имени источника.

    Сопоставляет имена источников (как в таблице `source`) с классами парсеров.
    Использует маппинг URL → короткое имя для сопоставления полных URL из БД.
    Каждый парсер создаётся один раз и переиспользуется.
    """

    # Маппинг URL источников из БД → короткие имена для парсеров
    URL_ALIASES: dict[str, str]

    _parsers: dict[str, Any]

    @classmethod
    def _init_registry(cls) -> None:
        """Ленивая инициализация реестров."""
        if not hasattr(cls, 'URL_ALIASES') or cls.URL_ALIASES is None:
            cls.URL_ALIASES = {
                'https://kad.arbitr.ru/': 'kad_arbitr',
                'https://fedresurs.ru/': 'fedresurs',
            }
        if not hasattr(cls, '_parsers') or cls._parsers is None:
            cls._parsers = {}

    @classmethod
    def resolve_name(cls, source_url: str) -> str | None:
        """Преобразовать URL источника в короткое имя парсера.

        Args:
            source_url: Полный URL из таблицы `source`.

        Returns:
            Короткое имя парсера или None, если не распознан.
        """
        cls._init_registry()
        # Exact match
        if source_url in cls.URL_ALIASES:
            return cls.URL_ALIASES[source_url]
        # Try to find by substring
        for url_pattern, short_name in cls.URL_ALIASES.items():
            if url_pattern in source_url:
                return short_name
        return None

    @classmethod
    def get_parser(cls, source_name: str) -> Any | None:
        """Вернуть экземпляр парсера для указанного имени источника.

        Args:
            source_name: Имя из таблицы `source`
                         (например, 'https://kad.arbitr.ru/').

        Returns:
            Экземпляр парсера или None, если источник не зарегистрирован.
        """
        cls._init_registry()
        short_name = cls.resolve_name(source_name)
        if short_name is None:
            return None
        return cls._parsers.get(short_name)

    @classmethod
    def register(cls, short_name: str, parser: Any) -> None:
        """Зарегистрировать экземпляр парсера для короткого имени источника."""
        cls._init_registry()
        cls._parsers[short_name] = parser


# ── Pipeline ─────────────────────────────────────────────────────────────────


class Pipeline:
    """Главный оркестратор пайплайна сбора данных.

    Загружает активные источники и поисковые задачи из PostgreSQL,
    затем для каждого активного источника → активного конкурента
    выполняет зарегистрированный парсер
    и сохраняет результаты через raw_storage.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.source_manager = SourceManager(max_errors=3)
        self.storage: RawDataRepository | None = None
        self._pipeline_run_id: str = uuid.uuid4().hex[:12]

    async def run(self) -> dict[str, Any]:
        """Выполнить полный пайплайн.

        Returns:
            Словарь со сводкой и метриками.
        """
        start_time = time.monotonic()
        JSONStructureLogger.info(
            'pipeline_started',
            pipeline_run_id=self._pipeline_run_id,
        )

        # ── 1. Init storage ──────────────────────────────────────────────
        disk_backend = DiskBackend(base_path='./data/raw')
        self.storage = RawDataRepository(storage_backend=disk_backend)

        # ── 2. Register parsers ──────────────────────────────────────────
        ParserFactory.register('kad_arbitr', KadArbitrParser())
        ParserFactory.register('fedresurs', FedresursRPA())
        JSONStructureLogger.info(
            'parsers_registered',
            pipeline_run_id=self._pipeline_run_id,
            parsers=list(ParserFactory._parsers.keys()),
        )

        # ── 3. Load active sources ───────────────────────────────────────
        sources = await self._load_active_sources()
        JSONStructureLogger.info(
            'sources_loaded',
            pipeline_run_id=self._pipeline_run_id,
            count=len(sources),
            sources=[s.name for s in sources],
        )

        # ── 4. Register sources in SourceManager ─────────────────────────
        for src in sources:
            self.source_manager.register(src.name)

        # ── 5. Load active search_tasks with relations ───────────────────
        search_tasks = await self._load_active_search_tasks()
        JSONStructureLogger.info(
            'search_tasks_loaded',
            pipeline_run_id=self._pipeline_run_id,
            count=len(search_tasks),
        )

        # ── 6. Main loop: source → competitor → parse → save ────────────
        total_competitors = 0
        successful_saves = 0
        failed_saves = 0

        for src in sources:
            if not self.source_manager.is_enabled(src.name):
                JSONStructureLogger.info(
                    'source_skipped_disabled',
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=src.name,
                )
                continue

            parser = ParserFactory.get_parser(src.name)
            if parser is None:
                JSONStructureLogger.warning(
                    'source_no_parser',
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=src.name,
                )
                continue

            # Filter tasks for this source
            source_tasks = [st for st in search_tasks if st.source_id == src.id]
            if not source_tasks:
                JSONStructureLogger.info(
                    'source_no_tasks',
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=src.name,
                )
                continue

            for task in source_tasks:
                if not self.source_manager.is_enabled(src.name):
                    break

                total_competitors += 1
                # Загружаем связанные данные по FK
                competitor = await self.session.get(
                    Competitor, task.competitor_id
                )
                trigger_obj = None
                if task.trigger_id is not None:
                    trigger_obj = await self.session.get(
                        Trigger, task.trigger_id
                    )
                trigger_keyword = trigger_obj.keyword if trigger_obj else ''

                JSONStructureLogger.info(
                    'task_processing',
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=src.name,
                    competitor_name=competitor.name,
                    task_id=task.id,
                    trigger_keyword=trigger_keyword,
                )

                success = await self._process_task(
                    parser=parser,
                    source_name=src.name,
                    competitor=competitor,
                    trigger_keyword=trigger_keyword,
                    task=task,
                )

                if success:
                    successful_saves += 1
                else:
                    failed_saves += 1

        # ── 7. Summary ───────────────────────────────────────────────────
        duration = time.monotonic() - start_time
        summary = {
            'pipeline_run_id': self._pipeline_run_id,
            'total_competitors': total_competitors,
            'successful_saves': successful_saves,
            'failed_saves': failed_saves,
            'sources_disabled': len(self.source_manager.disabled_sources),
            'disabled_sources': self.source_manager.disabled_sources,
            'duration_seconds': round(duration, 2),
        }

        JSONStructureLogger.info('pipeline_completed', **summary)
        return summary

    async def _load_active_sources(self) -> list[Source]:
        """Загрузить все активные источники из БД."""
        result = await self.session.execute(
            select(Source).where(Source.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def _load_active_search_tasks(self) -> list[SearchTask]:
        """Загрузить все активные поисковые задачи."""
        result = await self.session.execute(
            select(SearchTask).where(SearchTask.is_active.is_(True))
        )
        tasks = list(result.scalars().all())
        return tasks

    async def _process_task(
        self,
        parser: Any,
        source_name: str,
        competitor: Competitor,
        trigger_keyword: str,
        task: SearchTask,
    ) -> bool:
        """Обработать одну поисковую задачу с повторными попытками.

        Реализует экспоненциальную задержку (2^attempt секунд) и
        авто-отключение источника после 3 последовательных ошибок.
        """
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            task_start = time.monotonic()
            try:
                result = await self._execute_parser(
                    parser=parser,
                    source_name=source_name,
                    competitor=competitor,
                    trigger_keyword=trigger_keyword,
                )

                if result is None:
                    raise RuntimeError('Parser returned None')

                # ── Save to raw_storage (JSONB file) ────────────────────
                html_content = result.get('html_content', '')
                request_url = result.get('request_url', '')

                jsonb_path = await self._save_to_storage(
                    search_task_id=task.id,
                    source_name=source_name,
                    competitor_name=competitor.name,
                    trigger_keyword=trigger_keyword or competitor.inn or '',
                    html_content=html_content,
                    request_url=request_url,
                )

                # ── Save reference to RawItem in DB ─────────────────────
                content_hash = compute_content_hash(html_content)

                # Idempotency: проверяем, не сохраняли ли уже такой же хэш
                # для этой search_task. Если да — обновляем только updated_at.
                existing = await self._find_existing_by_hash(
                    search_task_id=task.id,
                    content_hash=content_hash,
                )
                if existing is not None:
                    duration_ms = int((time.monotonic() - task_start) * 1000)
                    JSONStructureLogger.info(
                        'task_duplicate_skipped',
                        pipeline_run_id=self._pipeline_run_id,
                        source_name=source_name,
                        competitor_name=competitor.name,
                        task_id=task.id,
                        status='duplicate',
                        content_hash=content_hash[:16],
                        duration_ms=duration_ms,
                    )
                    self.source_manager.reset_errors(source_name)
                    return True

                await self._save_raw_item(
                    search_task_id=task.id,
                    status=RawItemStatus.new,
                    content_hash=content_hash,
                    raw_data={
                        'source': source_name,
                        'competitor': competitor.name,
                        'trigger': trigger_keyword or competitor.inn or '',
                        'html_preview': html_content[:500],
                        'content_hash': content_hash,
                        'jsonb_path': jsonb_path,
                    },
                    html_file_path=jsonb_path,
                    source_request_url=request_url,
                )

                duration_ms = int((time.monotonic() - task_start) * 1000)
                JSONStructureLogger.info(
                    'task_success',
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=source_name,
                    competitor_name=competitor.name,
                    task_id=task.id,
                    status='success',
                    duration_ms=duration_ms,
                )

                self.source_manager.reset_errors(source_name)
                return True

            except Exception as e:
                duration_ms = int((time.monotonic() - task_start) * 1000)
                JSONStructureLogger.warning(
                    'task_retry',
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=source_name,
                    competitor_name=competitor.name,
                    task_id=task.id,
                    attempt=attempt,
                    max_retries=max_retries,
                    error=str(e),
                    duration_ms=duration_ms,
                )

                if attempt < max_retries:
                    backoff = 2**attempt
                    JSONStructureLogger.info(
                        'task_backoff',
                        pipeline_run_id=self._pipeline_run_id,
                        source_name=source_name,
                        competitor_name=competitor.name,
                        task_id=task.id,
                        backoff_seconds=backoff,
                    )
                    await asyncio.sleep(backoff)

        # ── All retries exhausted ────────────────────────────────────────
        error_msg = f'All {max_retries} attempts failed for task {task.id}'
        JSONStructureLogger.error(
            'task_failed',
            pipeline_run_id=self._pipeline_run_id,
            source_name=source_name,
            competitor_name=competitor.name,
            task_id=task.id,
            status='error',
            error=error_msg,
        )

        # Save error to RawItem
        await self._save_raw_item(
            search_task_id=task.id,
            status=RawItemStatus.error,
            error_message=error_msg,
        )

        # Increment error counter — may disable source
        was_disabled = self.source_manager.increment_error(source_name)
        if was_disabled:
            JSONStructureLogger.warning(
                'source_disabled_after_errors',
                pipeline_run_id=self._pipeline_run_id,
                source_name=source_name,
            )

        return False

    async def _execute_parser(
        self,
        parser: Any,
        source_name: str,
        competitor: Competitor,
        trigger_keyword: str,
    ) -> dict[str, str] | None:
        """Выполнить подходящий парсер в зависимости от типа источника.

        Сначала преобразует URL источника в короткое имя, затем диспетчеризует.

        Возвращает словарь с 'html_content' и 'request_url'
        или None при ошибке.
        """
        short_name = ParserFactory.resolve_name(source_name)
        if short_name == 'kad_arbitr':
            return await self._run_kad_arbitr(parser, competitor)
        elif short_name == 'fedresurs':
            return await self._run_fedresurs(
                parser, competitor, trigger_keyword
            )
        else:
            raise ValueError(
                f'Unknown source: {source_name} (resolved: {short_name})'
            )

    async def _run_kad_arbitr(
        self, parser: KadArbitrParser, competitor: Competitor
    ) -> dict[str, str]:
        """Запустить парсер kad_arbitr (синхронный, через executor)."""
        inn = competitor.inn
        if not inn:
            raise ValueError(f"Competitor '{competitor.name}' has no INN")

        request = KadRequest(
            inn=inn,
            headless=True,
            output_dir='./data/parsed_pages/kad_arbitr',
            retry_count=1,  # Pipeline handles retries
        )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, parser.search_by_inn, request)

        if not result.success:
            raise RuntimeError(result.error or 'kad_arbitr parse failed')

        # Read HTML from saved file
        if result.file_path:
            with open(result.file_path, encoding='utf-8') as f:
                html_content = f.read()
        else:
            raise RuntimeError('kad_arbitr returned no file_path')

        return {
            'html_content': html_content,
            'request_url': f'https://kad.arbitr.ru/?inn={inn}',
        }

    async def _run_fedresurs(
        self,
        parser: FedresursRPA,
        competitor: Competitor,
        trigger_keyword: str,
    ) -> dict[str, str]:
        """Запустить парсер fedresurs (асинхронный)."""
        request = FedresursRequest(
            name=competitor.name,
            inn=competitor.inn,
            headless=True,
            output_dir='./data/parsed_pages/fedresurs',
            retry_count=1,  # Pipeline handles retries
        )

        result = await parser.search(request)

        if not result.success:
            raise RuntimeError(result.error or 'fedresurs parse failed')

        # Read HTML from saved file
        if result.file_path:
            with open(result.file_path, encoding='utf-8') as f:
                html_content = f.read()
        elif result.html_content:
            html_content = result.html_content
        else:
            raise RuntimeError('fedresurs returned no content')

        return {
            'html_content': html_content,
            'request_url': (
                'https://fedresurs.ru/search?q='
                f'{competitor.inn or competitor.name}'
            ),
        }

    async def _save_to_storage(
        self,
        search_task_id: int,
        source_name: str,
        competitor_name: str,
        trigger_keyword: str,
        html_content: str,
        request_url: str,
    ) -> str:
        """Сохранить распарсенные данные как JSONB-файл через raw_storage.

        Возвращает путь к сохранённому JSONB-файлу.
        """
        raw_file = RawDataFile(
            meta=MetaInfo(
                search_task_id=search_task_id,
                source=source_name,
                competitor=competitor_name,
                trigger=trigger_keyword,
                source_request_url=request_url,
                fetched_at=datetime.now(UTC),
            ),
            items=[
                StorageItem(
                    url=request_url,
                    title=f'Parsed: {competitor_name}',
                    text=html_content,
                )
            ],
        )

        path = await self.storage.save(raw_file)
        return path

    async def _find_existing_by_hash(
        self,
        search_task_id: int,
        content_hash: str,
    ) -> RawItem | None:
        """Проверить, существует ли уже запись с таким хэшем для задачи.

        Idempotency: если контент не изменился — не создаём новую строку,
        а только обновляем updated_at у последней записи.

        Args:
            search_task_id: ID поисковой задачи.
            content_hash: SHA-256 хэш контента.

        Returns:
            Существующий RawItem или None, если дубликат не найден.
        """
        result = await self.session.execute(
            select(RawItem).where(
                RawItem.search_task_id == search_task_id,
                RawItem.content_hash == content_hash,
                RawItem.status != RawItemStatus.error,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            # Обновляем updated_at, чтобы отметить время последней сверки
            existing.updated_at = datetime.now(UTC)
            await self.session.commit()
        return existing

    async def _save_raw_item(
        self,
        search_task_id: int,
        status: RawItemStatus,
        content_hash: str | None = None,
        raw_data: dict[str, Any] | None = None,
        html_file_path: str | None = None,
        source_request_url: str | None = None,
        error_message: str | None = None,
    ) -> RawItem:
        """Сохранить запись RawItem в базу данных."""
        item = RawItem(
            search_task_id=search_task_id,
            status=status,
            content_hash=content_hash,
            raw_data=raw_data,
            html_file_path=html_file_path,
            source_request_url=source_request_url,
            error_message=error_message,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item


# ── Main Entry Point ─────────────────────────────────────────────────────────


async def main() -> dict[str, Any]:
    """Точка входа пайплайна.

    Настраивает структурированное логирование, создаёт сессию БД,
    запускает пайплайн и выводит сводку.

    Returns:
        Словарь со сводкой и метриками.
    """
    # ── Logging setup ────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z',
    )

    JSONStructureLogger.info('main_started')

    async with AsyncSessionLocal() as session:
        pipeline = Pipeline(session=session)
        try:
            summary = await pipeline.run()
            print('\n' + '=' * 60)
            print('СВОДКА ПАЙПЛАЙНА')
            print('=' * 60)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print('=' * 60 + '\n')
            return summary
        except Exception as e:
            JSONStructureLogger.error('main_failed', error=str(e))
            raise


if __name__ == '__main__':
    asyncio.run(main())
