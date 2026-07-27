#!/usr/bin/env python3
"""Production-Grade Competitive Intelligence Pipeline.

Orchestrates data collection from multiple sources (kad_arbitr, fedresurs)
and stores results as JSONB files via raw_storage.

Usage:
    python -m src.run_pipeline
"""

from __future__ import annotations
from src.bp1.collectors.fedresurs_rpa.models import (
    SearchRequest as FedresursRequest,
)
from src.bp1.collectors.fedresurs_rpa import FedresursRPA
from src.bp1.collectors.kad_arbitr_rpa.models import (
    ParsingRequest as KadRequest,
)
from src.bp1.collectors.kad_arbitr_rpa import KadArbitrParser
from src.bp1.models import (
    Competitor,
    RawItem,
    RawItemStatus,
    SearchTask,
    Source,
    Trigger,
)
from core.database import AsyncSessionLocal

import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Добавляем путь к raw_storage (он внутри src/bp1 и импортирует сам себя)
_src_bp1 = str(Path(__file__).resolve().parent / "bp1")
if _src_bp1 not in sys.path:
    sys.path.insert(0, _src_bp1)


# ── Parsers ──────────────────────────────────────────────────────────────────

# ── Raw Storage ──────────────────────────────────────────────────────────────
# NOTE: raw_storage использует внутренние импорты вида
# `from raw_storage.backends...`, поэтому sys.path должен включать src/bp1
from raw_storage import RawDataRepository  # noqa: E402
from raw_storage.backends.disk_backend import DiskBackend  # noqa: E402
from raw_storage.core.models import (  # noqa: E402
    MetaInfo,
    RawDataFile,
    RawDataItem as StorageItem,
)
from raw_storage.utils.hashing import compute_sha256  # noqa: E402

# ── Logging ──────────────────────────────────────────────────────────────────

logger = logging.getLogger("pipeline")


class JSONStructureLogger:
    """Structured JSON logging for pipeline events."""

    @staticmethod
    def _log(level: int, event: str, **kwargs: Any) -> None:
        record = {"event": event, "timestamp": datetime.now(
            timezone.utc).isoformat()}
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
    """Internal state for a single source."""
    error_count: int = 0
    max_errors: int = 3
    disabled: bool = False


class SourceManager:
    """Registry of parsers with error tracking and auto-disable.

    Tracks consecutive errors per source. After max_errors (default 3)
    consecutive failures, the source is automatically disabled for the
    remainder of the pipeline run.
    """

    def __init__(self, max_errors: int = 3) -> None:
        self._sources: Dict[str, SourceState] = {}
        self.max_errors = max_errors

    def register(self, name: str) -> None:
        """Register a source for tracking."""
        if name not in self._sources:
            self._sources[name] = SourceState(max_errors=self.max_errors)

    def increment_error(self, name: str) -> bool:
        """Increment error count for a source.

        Returns:
            True if source was just disabled (crossed max_errors threshold).
        """
        state = self._sources.get(name)
        if state is None:
            return False
        state.error_count += 1
        if state.error_count >= state.max_errors and not state.disabled:
            state.disabled = True
            JSONStructureLogger.warning(
                "source_disabled",
                source_name=name,
                error_count=state.error_count,
                max_errors=state.max_errors,
            )
            return True
        return False

    def reset_errors(self, name: str) -> None:
        """Reset error count on successful parse."""
        state = self._sources.get(name)
        if state is not None:
            state.error_count = 0

    def is_enabled(self, name: str) -> bool:
        """Check if source is still enabled."""
        state = self._sources.get(name)
        if state is None:
            return True
        return not state.disabled

    @property
    def disabled_sources(self) -> List[str]:
        """Return list of source names that have been disabled."""
        return [
            name for name, state in self._sources.items() if state.disabled
        ]


# ── ParserFactory ────────────────────────────────────────────────────────────


class ParserFactory:
    """Factory to instantiate parsers by source name.

    Maps source names (as stored in the `source` table) to parser classes.
    Uses a URL-to-name mapping to match full URLs from the DB to short names.
    Each parser is instantiated once and reused.
    """

    # Маппинг URL источников из БД → короткие имена для парсеров
    URL_ALIASES: Dict[str, str] = {
        "https://kad.arbitr.ru/": "kad_arbitr",
        "https://fedresurs.ru/": "fedresurs",
    }

    _parsers: Dict[str, Any] = {}

    @classmethod
    def resolve_name(cls, source_url: str) -> Optional[str]:
        """Resolve a source URL to a short parser name.

        Args:
            source_url: Full URL from the `source` table.

        Returns:
            Short parser name or None if not recognized.
        """
        # Exact match
        if source_url in cls.URL_ALIASES:
            return cls.URL_ALIASES[source_url]
        # Try to find by substring
        for url_pattern, short_name in cls.URL_ALIASES.items():
            if url_pattern in source_url:
                return short_name
        return None

    @classmethod
    def get_parser(cls, source_name: str) -> Optional[Any]:
        """Return a parser instance for the given source name.

        Args:
            source_name: Name from the `source` table
                         (e.g. 'https://kad.arbitr.ru/').

        Returns:
            Parser instance or None if source is not registered.
        """
        short_name = cls.resolve_name(source_name)
        if short_name is None:
            return None
        return cls._parsers.get(short_name)

    @classmethod
    def register(cls, short_name: str, parser: Any) -> None:
        """Register a parser instance for a short source name."""
        cls._parsers[short_name] = parser


# ── Pipeline ─────────────────────────────────────────────────────────────────


class Pipeline:
    """Main orchestrator for the collection pipeline.

    Loads active sources and search tasks from PostgreSQL, then for each
    active source → active competitor → executes the registered parser
    and saves results via raw_storage.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.source_manager = SourceManager(max_errors=3)
        self.storage: Optional[RawDataRepository] = None
        self._pipeline_run_id: str = uuid.uuid4().hex[:12]

    async def run(self) -> Dict[str, Any]:
        """Execute the full pipeline.

        Returns:
            Summary dict with metrics.
        """
        start_time = time.monotonic()
        JSONStructureLogger.info(
            "pipeline_started",
            pipeline_run_id=self._pipeline_run_id,
        )

        # ── 1. Init storage ──────────────────────────────────────────────
        disk_backend = DiskBackend(base_path="./data/raw")
        self.storage = RawDataRepository(storage_backend=disk_backend)

        # ── 2. Register parsers ──────────────────────────────────────────
        ParserFactory.register("kad_arbitr", KadArbitrParser())
        ParserFactory.register("fedresurs", FedresursRPA())
        JSONStructureLogger.info(
            "parsers_registered",
            pipeline_run_id=self._pipeline_run_id,
            parsers=list(ParserFactory._parsers.keys()),
        )

        # ── 3. Load active sources ───────────────────────────────────────
        sources = await self._load_active_sources()
        JSONStructureLogger.info(
            "sources_loaded",
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
            "search_tasks_loaded",
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
                    "source_skipped_disabled",
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=src.name,
                )
                continue

            parser = ParserFactory.get_parser(src.name)
            if parser is None:
                JSONStructureLogger.warning(
                    "source_no_parser",
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=src.name,
                )
                continue

            # Filter tasks for this source
            source_tasks = [
                st for st in search_tasks if st.source_id == src.id]
            if not source_tasks:
                JSONStructureLogger.info(
                    "source_no_tasks",
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
                trigger_keyword = (
                    trigger_obj.keyword if trigger_obj else ""
                )

                JSONStructureLogger.info(
                    "task_processing",
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
            "pipeline_run_id": self._pipeline_run_id,
            "total_competitors": total_competitors,
            "successful_saves": successful_saves,
            "failed_saves": failed_saves,
            "sources_disabled": len(self.source_manager.disabled_sources),
            "disabled_sources": self.source_manager.disabled_sources,
            "duration_seconds": round(duration, 2),
        }

        JSONStructureLogger.info("pipeline_completed", **summary)
        return summary

    async def _load_active_sources(self) -> List[Source]:
        """Load all active sources from DB."""
        result = await self.session.execute(
            select(Source).where(Source.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def _load_active_search_tasks(self) -> List[SearchTask]:
        """Load all active search tasks."""
        result = await self.session.execute(
            select(SearchTask)
            .where(SearchTask.is_active.is_(True))
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
        """Process a single search task with retry logic.

        Implements exponential backoff (2^attempt seconds) and
        source auto-disable after 3 consecutive failures.
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
                    raise RuntimeError("Parser returned None")

                # ── Save to raw_storage (JSONB file) ────────────────────
                html_content = result.get("html_content", "")
                request_url = result.get("request_url", "")

                jsonb_path = await self._save_to_storage(
                    search_task_id=task.id,
                    source_name=source_name,
                    competitor_name=competitor.name,
                    trigger_keyword=trigger_keyword or competitor.inn or "",
                    html_content=html_content,
                    request_url=request_url,
                )

                # ── Save reference to RawItem in DB ─────────────────────
                content_hash = compute_sha256(html_content.encode("utf-8"))
                await self._save_raw_item(
                    search_task_id=task.id,
                    status=RawItemStatus.new,
                    content_hash=content_hash,
                    raw_data={
                        "source": source_name,
                        "competitor": competitor.name,
                        "trigger": trigger_keyword or competitor.inn or "",
                        "html_preview": html_content[:500],
                        "content_hash": content_hash,
                        "jsonb_path": jsonb_path,
                    },
                    html_file_path=jsonb_path,
                    source_request_url=request_url,
                )

                duration_ms = int((time.monotonic() - task_start) * 1000)
                JSONStructureLogger.info(
                    "task_success",
                    pipeline_run_id=self._pipeline_run_id,
                    source_name=source_name,
                    competitor_name=competitor.name,
                    task_id=task.id,
                    status="success",
                    duration_ms=duration_ms,
                )

                self.source_manager.reset_errors(source_name)
                return True

            except Exception as e:
                duration_ms = int((time.monotonic() - task_start) * 1000)
                JSONStructureLogger.warning(
                    "task_retry",
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
                    backoff = 2 ** attempt
                    JSONStructureLogger.info(
                        "task_backoff",
                        pipeline_run_id=self._pipeline_run_id,
                        source_name=source_name,
                        competitor_name=competitor.name,
                        task_id=task.id,
                        backoff_seconds=backoff,
                    )
                    await asyncio.sleep(backoff)

        # ── All retries exhausted ────────────────────────────────────────
        error_msg = f"All {max_retries} attempts failed for task {task.id}"
        JSONStructureLogger.error(
            "task_failed",
            pipeline_run_id=self._pipeline_run_id,
            source_name=source_name,
            competitor_name=competitor.name,
            task_id=task.id,
            status="error",
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
                "source_disabled_after_errors",
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
    ) -> Optional[Dict[str, str]]:
        """Execute the appropriate parser based on source type.

        Resolves the source URL to a short name first, then dispatches.

        Returns dict with 'html_content' and 'request_url' or None on failure.
        """
        short_name = ParserFactory.resolve_name(source_name)
        if short_name == "kad_arbitr":
            return await self._run_kad_arbitr(parser, competitor)
        elif short_name == "fedresurs":
            return await self._run_fedresurs(
                parser, competitor, trigger_keyword
            )
        else:
            raise ValueError(
                f"Unknown source: {source_name} (resolved: {short_name})"
            )

    async def _run_kad_arbitr(
        self, parser: KadArbitrParser, competitor: Competitor
    ) -> Dict[str, str]:
        """Run kad_arbitr parser (sync, run in executor)."""
        inn = competitor.inn
        if not inn:
            raise ValueError(f"Competitor '{competitor.name}' has no INN")

        request = KadRequest(
            inn=inn,
            headless=True,
            output_dir="./data/parsed_pages/kad_arbitr",
            retry_count=1,  # Pipeline handles retries
        )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, parser.search_by_inn, request
        )

        if not result.success:
            raise RuntimeError(result.error or "kad_arbitr parse failed")

        # Read HTML from saved file
        if result.file_path:
            with open(result.file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        else:
            raise RuntimeError("kad_arbitr returned no file_path")

        return {
            "html_content": html_content,
            "request_url": f"https://kad.arbitr.ru/?inn={inn}",
        }

    async def _run_fedresurs(
        self,
        parser: FedresursRPA,
        competitor: Competitor,
        trigger_keyword: str,
    ) -> Dict[str, str]:
        """Run fedresurs parser (async)."""
        request = FedresursRequest(
            name=competitor.name,
            inn=competitor.inn,
            headless=True,
            output_dir="./data/parsed_pages/fedresurs",
            retry_count=1,  # Pipeline handles retries
        )

        result = await parser.search(request)

        if not result.success:
            raise RuntimeError(result.error or "fedresurs parse failed")

        # Read HTML from saved file
        if result.file_path:
            with open(result.file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        elif result.html_content:
            html_content = result.html_content
        else:
            raise RuntimeError("fedresurs returned no content")

        return {
            "html_content": html_content,
            "request_url": (
                "https://fedresurs.ru/search?q="
                f"{competitor.inn or competitor.name}"
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
        """Save parsed data as a JSONB file via raw_storage.

        Returns the path to the saved JSONB file.
        """
        raw_file = RawDataFile(
            meta=MetaInfo(
                search_task_id=search_task_id,
                source=source_name,
                competitor=competitor_name,
                trigger=trigger_keyword,
                source_request_url=request_url,
                fetched_at=datetime.now(timezone.utc),
            ),
            items=[
                StorageItem(
                    url=request_url,
                    title=f"Parsed: {competitor_name}",
                    text=html_content,
                )
            ],
        )

        path = await self.storage.save(raw_file)
        return path

    async def _save_raw_item(
        self,
        search_task_id: int,
        status: RawItemStatus,
        content_hash: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        html_file_path: Optional[str] = None,
        source_request_url: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> RawItem:
        """Save a RawItem record to the database."""
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


async def main() -> Dict[str, Any]:
    """Pipeline entry point.

    Sets up structured logging, creates a DB session, runs the pipeline,
    and prints the summary.

    Returns:
        Summary dict with metrics.
    """
    # ── Logging setup ────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    JSONStructureLogger.info("main_started")

    async with AsyncSessionLocal() as session:
        pipeline = Pipeline(session=session)
        try:
            summary = await pipeline.run()
            print("\n" + "=" * 60)
            print("PIPELINE SUMMARY")
            print("=" * 60)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print("=" * 60 + "\n")
            return summary
        except Exception as e:
            JSONStructureLogger.error("main_failed", error=str(e))
            raise


if __name__ == "__main__":
    asyncio.run(main())
