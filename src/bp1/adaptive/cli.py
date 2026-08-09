"""
CLI интерфейс для адаптивного сбора данных (BP-1 Adaptive).

Источник ``--source`` принимается в любом виде: ``lenta.ru``,
``https://lenta.ru/`` или ``https://www.lenta.ru/news`` — внутри он
нормализуется до канонического hostname, поэтому профиль, адаптер и
классификация находятся независимо от формы ввода.

Использование:
    # Запуск всех задач (run_all: сбор по всем источникам из БД)
    python -m src.bp1.adaptive.cli run

    # Запуск адаптивного сбора
    python -m src.bp1.adaptive.cli run --source lenta.ru \
        --competitor "ООО АРХИТЕХ ИИ"

    # Запуск с указанием режима
    python -m src.bp1.adaptive.cli run --source lenta.ru \
        --mode hybrid --fallback

    # Классификация источника
    python -m src.bp1.adaptive.cli classify --source lenta.ru

    # Регистрация нового источника (нормализация + классификация + БД + Redis)
    python -m src.bp1.adaptive.cli add-source --url "https://www.lenta.ru/news"

    # Управление кэшем адаптеров (источник можно указывать в любом виде:
    # lenta.ru или https://lenta.ru/ — ключ нормализуется до hostname)
    python -m src.bp1.adaptive.cli cache --show --source lenta.ru
    python -m src.bp1.adaptive.cli cache --show --source https://lenta.ru/
    python -m src.bp1.adaptive.cli cache --clear --source lenta.ru

    # Управление профилями браузеров (профиль ищется и в data/cache/profiles,
    # и в data/profiles — независимо от формы ввода источника)
    python -m src.bp1.adaptive.cli profile --show --source lenta.ru
    python -m src.bp1.adaptive.cli profile --show --source https://lenta.ru/

    # Отчет качества
    python -m src.bp1.adaptive.cli quality --report --task-id 26
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.bp1.constants import DEFAULT_TIMEOUT_MS

# Добавляем корень проекта в PYTHONPATH
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# core.config (pydantic-settings) читает .env только в СВОИ поля, а не в
# os.environ — а llm.py читает LLM_*/OPENAI_API_KEY/DEEPSEEK_API_KEY именно
# через os.getenv(). Без явной загрузки .env сюда эти ключи не долетают,
# и адаптивный парсер молча уходит в эвристический fallback.
load_dotenv(_PROJECT_ROOT / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


async def _run_command(args: argparse.Namespace) -> None:
    """Команда run: запуск адаптивного сбора."""
    from core.database import AsyncSessionLocal
    from core.redis_client import get_redis

    from .integration.runner import AdaptiveRunner

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
            elif args.source or args.competitor:
                # Отдельный сбор по конкретной паре источник + конкурент:
                # создаёт/находит Source, Competitor, SearchTask в БД и
                # запускает именно эту задачу (не run_all).
                if not args.source:
                    logger.error(
                        'Для сбора по конкретному конкуренту '
                        'обязательно укажите --source'
                    )
                    return
                result = await runner.run_source_competitor(
                    args.source,
                    args.competitor,
                    session,
                    redis,
                )
                logger.info('Result: %s', result)
            else:
                results = await runner.run_all(session, redis)
                for result in results:
                    logger.info('Result: %s', result)
    finally:
        await redis.aclose()


async def _classify_command(args: argparse.Namespace) -> None:
    """Команда classify: классификация источника."""
    from .strategies.classifier import SourceClassifier

    classifier = SourceClassifier()
    classification = await classifier.classify(
        source_name=args.source,
        source_url=args.source,
    )
    print(classification.model_dump_json(indent=2))


async def _add_source_command(args: argparse.Namespace) -> None:
    """Команда add-source: регистрация нового источника по ссылке."""
    from core.database import AsyncSessionLocal
    from core.redis_client import get_redis

    from .integration.sources import SourceRegistrationService

    redis = await get_redis()
    try:
        async with AsyncSessionLocal() as session:
            service = SourceRegistrationService(session, redis_client=redis)
            result = await service.register(args.url)
            await session.commit()

            print(f'Источник: {result.source_name}')
            print(f'  host      : {result.host}')
            print(f'  created   : {result.created}')
            print(f'  source_id : {result.source_id}')
            cls = result.classification
            print(f'  type      : {cls.source_type.value}')
            print(f'  strategy  : {cls.recommended_strategy}')
            print(f'  complexity: {cls.complexity_score}')
    finally:
        await redis.aclose()


async def _cache_command(args: argparse.Namespace) -> None:
    """Команда cache: управление кэшем адаптеров.

    Подключает Redis (адаптеры хранятся там) и нормализует источник до
    канонического hostname, чтобы ``--source lenta.ru`` и
    ``--source https://lenta.ru/`` давали один и тот же ключ.
    """
    from core.redis_client import get_redis

    from .core.cache import UnifiedCache

    redis = await get_redis()
    try:
        cache = UnifiedCache(redis_client=redis)

        if args.clear:
            await cache.clear_adapter(args.source)
            print(f'Adapter cache cleared for {args.source}')
        else:
            adapter = await cache.get_adapter(args.source)
            if adapter is None:
                print(f'No adapter cached for {args.source}')
            else:
                print(adapter.model_dump_json(indent=2))
    finally:
        await redis.aclose()


async def _profile_command(args: argparse.Namespace) -> None:
    """Команда profile: управление профилями браузеров.

    Профили браузеров хранятся на диске. Источник нормализуется до
    канонического hostname, поэтому ``--source lenta.ru`` и
    ``--source https://lenta.ru/`` находят один и тот же профиль.
    Профиль ищется и в едином хранилище кэша, и в директории профилей HITL.
    """
    from pathlib import Path

    from .core.cache import UnifiedCache, _canonical_source_name

    cache = UnifiedCache()
    source = _canonical_source_name(args.source)

    # 1. Единое хранилище профилей UnifiedCache (data/cache/profiles).
    profile = await cache.get_profile(source)
    # 2. Fallback — директория профилей HITL (data/profiles).
    if profile is None:
        hitl_profile_path = Path('./src/bp1/data/profiles') / f'{source}.json'
        if hitl_profile_path.exists():
            import json

            try:
                profile = json.loads(
                    hitl_profile_path.read_text(encoding='utf-8')
                )
            except Exception:
                profile = None

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
    run_parser.add_argument('--source', default=None)
    run_parser.add_argument('--competitor', default='')
    run_parser.add_argument(
        '--mode',
        default='adaptive',
        choices=['adaptive', 'hybrid', 'fallback'],
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

    # add-source
    add_source_parser = subparsers.add_parser(
        'add-source', help='Регистрация нового источника по ссылке'
    )
    add_source_parser.add_argument('--url', required=True)
    add_source_parser.set_defaults(func=_add_source_command)

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
