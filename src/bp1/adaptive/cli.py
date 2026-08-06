#!/usr/bin/env python3
# src/bp1/adaptive/cli.py
"""
CLI интерфейс для адаптивного сбора данных (BP-1 Adaptive).

Использование:
    # Запуск адаптивного сбора
    python -m src.bp1.adaptive.cli run --source lenta.ru \
        --competitor "ООО АРХИТЕХ ИИ"

    # Запуск с указанием режима
    python -m src.bp1.adaptive.cli run --source lenta.ru \
        --mode hybrid --fallback

    # Классификация источника
    python -m src.bp1.adaptive.cli classify --source lenta.ru

    # Управление кэшем адаптеров
    python -m src.bp1.adaptive.cli cache --show --source lenta.ru
    python -m src.bp1.adaptive.cli cache --clear --source lenta.ru

    # Управление профилями браузеров
    python -m src.bp1.adaptive.cli profile --show --source lenta.ru

    # Отчет качества
    python -m src.bp1.adaptive.cli quality --report --task-id 26
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.bp1.constants import DEFAULT_TIMEOUT_MS

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


async def _run_command(args: argparse.Namespace) -> None:
    """Команда run: запуск адаптивного сбора."""
    from core.database import AsyncSessionLocal
    from core.redis_client import get_redis

    from .runner import AdaptiveRunner

    runner = AdaptiveRunner(
        mode=args.mode,
        headless=not args.no_headless,
        timeout=args.timeout,
    )

    redis = await get_redis()
    try:
        async with AsyncSessionLocal() as session:
            if args.task_id:
                result = await runner.run_task(args.task_id, session, redis)
                logger.info('Result: %s', result)
            else:
                results = await runner.run_all(session, redis)
                for result in results:
                    logger.info('Result: %s', result)
    finally:
        await redis.aclose()


async def _classify_command(args: argparse.Namespace) -> None:
    """Команда classify: классификация источника."""
    from .classifier import SourceClassifier

    classifier = SourceClassifier()
    classification = await classifier.classify(
        source_name=args.source,
        source_url=args.source,
    )
    print(classification.model_dump_json(indent=2))


async def _cache_command(args: argparse.Namespace) -> None:
    """Команда cache: управление кэшем адаптеров."""
    from .cache import UnifiedCache

    cache = UnifiedCache()

    if args.clear:
        await cache.clear_adapter(args.source)
        print(f'Adapter cache cleared for {args.source}')
    else:
        adapter = await cache.get_adapter(args.source)
        if adapter is None:
            print(f'No adapter cached for {args.source}')
        else:
            print(adapter.model_dump_json(indent=2))


async def _profile_command(args: argparse.Namespace) -> None:
    """Команда profile: управление профилями браузеров."""
    from .cache import UnifiedCache

    cache = UnifiedCache()
    profile = await cache.get_profile(args.source)
    if profile is None:
        print(f'No profile for {args.source}')
    else:
        print(profile)


async def _quality_command(args: argparse.Namespace) -> None:
    """Команда quality: отчёт качества."""
    from sqlalchemy import select

    from core.database import AsyncSessionLocal
    from src.bp1.models import RawItem

    async with AsyncSessionLocal() as session:
        stmt = (
            select(RawItem)
            .where(RawItem.search_task_id == args.task_id)
            .order_by(RawItem.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        raw_item = result.scalar_one_or_none()

        if raw_item is None:
            print(f'No raw item for task {args.task_id}')
            return

        print(f'RawItem #{raw_item.id}: status={raw_item.status}')
        print(f'  content_hash={raw_item.content_hash}')
        print(f'  created_at={raw_item.created_at}')
        if raw_item.raw_data:
            items = raw_item.raw_data.get('items', [])
            print(f'  items_count={len(items)}')


def build_parser() -> argparse.ArgumentParser:
    """Строит парсер аргументов CLI."""
    parser = argparse.ArgumentParser(
        prog='bp1-adaptive',
        description='Адаптивный сбор данных (BP-1 Adaptive)',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # run
    run_parser = subparsers.add_parser('run', help='Запуск адаптивного сбора')
    run_parser.add_argument('--source', default='adaptive')
    run_parser.add_argument('--competitor', default='')
    run_parser.add_argument(
        '--mode', default='adaptive', choices=['adaptive', 'hybrid', 'fallback']
    )
    run_parser.add_argument('--fallback', action='store_true')
    run_parser.add_argument('--task-id', type=int, default=None)
    run_parser.add_argument('--no-headless', action='store_true')
    run_parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT_MS)
    run_parser.set_defaults(func=_run_command)

    # classify
    classify_parser = subparsers.add_parser(
        'classify', help='Классификация источника'
    )
    classify_parser.add_argument('--source', required=True)
    classify_parser.set_defaults(func=_classify_command)

    # cache
    cache_parser = subparsers.add_parser(
        'cache', help='Управление кэшем адаптеров'
    )
    cache_parser.add_argument('--source', required=True)
    cache_parser.add_argument('--show', action='store_true')
    cache_parser.add_argument('--clear', action='store_true')
    cache_parser.set_defaults(func=_cache_command)

    # profile
    profile_parser = subparsers.add_parser(
        'profile', help='Управление профилями браузеров'
    )
    profile_parser.add_argument('--source', required=True)
    profile_parser.add_argument('--show', action='store_true')
    profile_parser.set_defaults(func=_profile_command)

    # quality
    quality_parser = subparsers.add_parser('quality', help='Отчёт качества')
    quality_parser.add_argument('--report', action='store_true')
    quality_parser.add_argument('--task-id', type=int, required=True)
    quality_parser.set_defaults(func=_quality_command)

    return parser


def main() -> None:
    """Точка входа CLI."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == '__main__':
    main()
