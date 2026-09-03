#!/usr/bin/env python3
"""Единый CLI этапа BP-1 (сбор данных).

Заменил два прежних интерфейса — `src/bp1/cli.py` (классический контур:
run/list/clear-redis) и `src/bp1/adaptive/cli.py` (адаптивный:
run/classify/add-source/cache/profile/quality): рабочие сценарии были
размазаны по двум точкам входа с разными флагами для одного и того же.

Четыре команды сбора — тонкие обёртки над заданиями `src/bp1/jobs.py`;
вся логика живёт там, поэтому планировщик задач может вызывать те же
функции напрямую, без CLI.

Использование:
    # 1. Собрать один источник по всем активным конкурентам
    python -m src.bp1.cli source lenta.ru

    # 2. Собрать одного конкурента по всем активным источникам
    #    (конкурента, которого нет в БД, задание создаст само)
    python -m src.bp1.cli competitor "Сбербанк"
    python -m src.bp1.cli competitor "Сбербанк" --inn 7707083893

    # 3. Собрать ровно одну пару источник + конкурент (без всей матрицы)
    python -m src.bp1.cli source-competitor lenta.ru "Сбербанк"

    # 4. Полный прогон: все источники x все конкуренты
    python -m src.bp1.cli all
    python -m src.bp1.cli all --no-ensure-matrix   # только заведённые связки

    # 5. Поставить новый источник на учёт (категоризация + БД + кэш)
    python -m src.bp1.cli add-source https://www.lenta.ru/news

Диагностика (вспомогательные команды):
    python -m src.bp1.cli list                       # активные связки
    python -m src.bp1.cli classify lenta.ru          # категоризация без записи
    python -m src.bp1.cli cache --show lenta.ru      # адаптер источника
    python -m src.bp1.cli cache --clear lenta.ru
    python -m src.bp1.cli quality --task-id 26       # последний RawItem задачи
    python -m src.bp1.cli clear-redis                # сброс хэшей дедупликации

Источник в любой команде принимается в любой форме: `lenta.ru`,
`https://lenta.ru/` или `https://www.lenta.ru/news` — внутри он
нормализуется до канонического hostname, поэтому адаптер, классификация и
профиль находятся независимо от формы ввода.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Корень проекта в PYTHONPATH — чтобы `python src/bp1/cli.py` работал так же,
# как `python -m src.bp1.cli`.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

_SEPARATOR = '=' * 60


# ============================================================================
# ВЫВОД
# ============================================================================


def _print_failure_summary(summary: dict[str, Any], status: str) -> None:
    """Печатает сводку неуспешного прогона (status != 'ok')."""
    print(f'Результат: {status}')
    for key in ('source', 'competitor'):
        if summary.get(key):
            print(f'  {key}: {summary[key]}')
    print(_SEPARATOR)


def _print_job_header(summary: dict[str, Any]) -> None:
    """Печатает задание и его источники/конкурентов."""
    print(f'Задание: {summary.get("job", "?")}')
    for key, label in (
        ('source', 'источник'),
        ('competitor', 'конкурент'),
        ('sources', 'источников'),
        ('competitors', 'конкурентов'),
    ):
        if summary.get(key) is not None:
            print(f'  {label}: {summary[key]}')


def _print_task_counts(summary: dict[str, Any]) -> None:
    """Печатает счётчики задач и итоговый процент успеха."""
    print(f'  задач: {summary.get("tasks", 0)}')
    print(f'    сохранено      : {summary.get("saved", 0)}')
    print(f'    без изменений  : {summary.get("unchanged", 0)}')
    print(f'    ошибок         : {summary.get("error", 0)}')
    print(f'    пропущено      : {summary.get("skipped", 0)}')
    print(f'  успех: {summary.get("success_rate", 0.0) * 100:.1f}%')


def _print_strategy_breakdown(summary: dict[str, Any]) -> None:
    """Печатает разбивку по фактически сработавшим стратегиям."""
    by_strategy = summary.get('by_strategy') or {}
    if not by_strategy:
        return
    print('  стратегии (фактические):')
    for name, count in sorted(by_strategy.items(), key=lambda kv: -kv[1]):
        print(f'    {name:<10} {count}')


def _print_quality_failures(summary: dict[str, Any]) -> None:
    """Печатает провалы контроля качества и источники низкого качества."""
    quality = summary.get('quality_levels') or {}
    failed = {
        level: info
        for level, info in quality.items()
        if isinstance(info, dict) and info.get('failed')
    }
    if failed:
        print('  контроль качества (провалы):')
        for level, info in failed.items():
            print(f'    {level:<12} не прошло: {info["failed"]}')

    low_quality = summary.get('low_quality_sources') or []
    if low_quality:
        print(f'  низкое качество у источников: {", ".join(low_quality)}')


def _print_pair_result(result: dict[str, Any]) -> None:
    """Печатает результат прогона одной пары источник+конкурент
    (:func:`~src.bp1.jobs.collect_source_competitor` — не сводка по
    батчу задач, как :func:`_print_summary`, а один ``RawItem``)."""
    print()
    print(_SEPARATOR)
    status = result.get('status', '?')
    print(f'Статус: {status}')
    for key, label in (
        ('source', 'источник'),
        ('reason', 'причина'),
        ('raw_item_id', 'raw_item_id'),
        ('hash', 'хэш'),
        ('strategy', 'стратегия'),
        ('source_items', 'элементов'),
        ('empty_reason', 'причина пустоты'),
    ):
        if result.get(key) is not None:
            print(f'  {label}: {result[key]}')
    quality = result.get('quality_levels') or {}
    failed = {
        level: info
        for level, info in quality.items()
        if isinstance(info, dict) and info.get('failed')
    }
    if failed:
        print('  контроль качества (провалы):')
        for level, info in failed.items():
            print(f'    {level:<12} не прошло: {info["failed"]}')
    print(_SEPARATOR)


def _print_summary(summary: dict[str, Any]) -> None:
    """Печатает сводку прогона в человекочитаемом виде."""
    print()
    print(_SEPARATOR)
    status = summary.get('status')
    if status and status != 'ok':
        _print_failure_summary(summary, status)
        return

    _print_job_header(summary)
    _print_task_counts(summary)
    _print_strategy_breakdown(summary)
    _print_quality_failures(summary)
    print(_SEPARATOR)


# ============================================================================
# КОМАНДЫ СБОРА (обёртки над jobs.py)
# ============================================================================


async def _cmd_source(args: argparse.Namespace) -> None:
    """Сбор по одному источнику (все активные конкуренты)."""
    from src.bp1.jobs import collect_source

    summary = await collect_source(
        args.source,
        headless=not args.no_headless,
        timeout=args.timeout,
        max_concurrent=args.max_concurrent,
    )
    _print_summary(summary)


async def _cmd_competitor(args: argparse.Namespace) -> None:
    """Сбор по одному конкуренту (все активные источники)."""
    from src.bp1.jobs import collect_competitor

    summary = await collect_competitor(
        args.competitor,
        inn=args.inn,
        headless=not args.no_headless,
        timeout=args.timeout,
        max_concurrent=args.max_concurrent,
    )
    if summary.get('competitor_created'):
        print(f'Конкурент «{summary["competitor"]}» добавлен в БД.')
    _print_summary(summary)


async def _cmd_all(args: argparse.Namespace) -> None:
    """Полный прогон: все источники x все конкуренты."""
    from src.bp1.jobs import collect_all

    summary = await collect_all(
        headless=not args.no_headless,
        timeout=args.timeout,
        max_concurrent=args.max_concurrent,
        ensure_matrix=not args.no_ensure_matrix,
    )
    _print_summary(summary)


async def _cmd_source_competitor(args: argparse.Namespace) -> None:
    """Сбор по конкретной паре источник + конкурент (без обхода всей
    матрицы связок)."""
    from src.bp1.jobs import collect_source_competitor

    result = await collect_source_competitor(
        args.source,
        args.competitor,
        inn=args.inn,
        headless=not args.no_headless,
        timeout=args.timeout,
    )
    _print_pair_result(result)


async def _cmd_add_source(args: argparse.Namespace) -> None:
    """Постановка нового источника на учёт."""
    from src.bp1.jobs import register_source

    result = await register_source(args.url)

    print()
    print(_SEPARATOR)
    print(f'Источник: {result["source"]}')
    print(f'  host      : {result["host"]}')
    print(f'  создан    : {result["created"]}')
    print(f'  source_id : {result["source_id"]}')
    cls = result['classification']
    print(f'  тип       : {cls["source_type"]}')
    print(f'  стратегия : {cls["recommended_strategy"]}')
    print(f'  сложность : {cls["complexity_score"]}')
    print(f'  антибот   : {cls["has_antibot"]}, CAPTCHA: {cls["has_captcha"]}')
    probe = result.get('search_probe')
    if probe:
        param = next(iter(probe.get('search_params') or {}), '?')
        print(f'  поиск     : OK ({probe["search_method"]}, {param}=)')
        print(f'  search_url: {probe["search_url"]}')
    else:
        print(
            '  поиск     : не подтверждён '
            '(эндпоинт не ответил — сбор пойдёт по шаблону)'
        )
    print(_SEPARATOR)


# ============================================================================
# ДИАГНОСТИЧЕСКИЕ КОМАНДЫ
# ============================================================================


async def _cmd_list(args: argparse.Namespace) -> None:
    """Показать активные связки источник-конкурент."""
    from sqlalchemy import select

    from core.database import AsyncSessionLocal
    from src.bp1.models import SearchTask

    async with AsyncSessionLocal() as session:
        stmt = (
            select(SearchTask)
            .where(SearchTask.is_active.is_(True))
            .order_by(SearchTask.id)
        )
        tasks = (await session.execute(stmt)).scalars().all()

        print()
        print(f'Активные связки: {len(tasks)}')
        print(_SEPARATOR)
        for task in tasks:
            trigger = task.trigger.keyword if task.trigger else '-'
            print(
                f'  #{task.id:<5} {task.source.name:<32} '
                f'{task.competitor.name:<28} триггер: {trigger}'
            )


async def _cmd_classify(args: argparse.Namespace) -> None:
    """Категоризация источника без записи в БД."""
    from src.bp1.adaptive.strategies.classifier import SourceClassifier

    classification = await SourceClassifier().classify(
        source_name=args.source,
        source_url=args.source,
    )
    print(classification.model_dump_json(indent=2))


async def _cmd_cache(args: argparse.Namespace) -> None:
    """Просмотр и сброс кэша адаптера источника."""
    from core.redis_client import get_redis
    from src.bp1.adaptive.core.cache import UnifiedCache

    redis = await get_redis()
    try:
        cache = UnifiedCache(redis_client=redis)
        if args.clear:
            await cache.clear_adapter(args.source)
            print(f'Кэш адаптера очищен: {args.source}')
            return
        adapter = await cache.get_adapter(args.source)
        if adapter is None:
            print(f'Адаптер не закэширован: {args.source}')
        else:
            print(adapter.model_dump_json(indent=2))
    finally:
        await redis.aclose()


async def _cmd_quality(args: argparse.Namespace) -> None:
    """Последний собранный RawItem по задаче."""
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
        raw_item = (await session.execute(stmt)).scalar_one_or_none()

        if raw_item is None:
            print(f'Нет данных по задаче {args.task_id}')
            return

        print(f'RawItem #{raw_item.id}: status={raw_item.status}')
        print(f'  content_hash : {raw_item.content_hash}')
        print(f'  created_at   : {raw_item.created_at}')
        if raw_item.raw_data:
            items = raw_item.raw_data.get('items', [])
            print(f'  items        : {len(items)}')
            levels = None
            for item in items:
                levels = (item.get('extra') or {}).get('quality_levels')
                if levels:
                    break
            if levels:
                dumped = json.dumps(levels, ensure_ascii=False)
                print(f'  quality      : {dumped}')


async def _cmd_clear_redis(args: argparse.Namespace) -> None:
    """Очистить ключи дедупликации BP-1 в Redis."""
    from core.database import AsyncSessionLocal
    from core.redis_client import redis_client

    redis = await redis_client.get_client()
    try:
        async with AsyncSessionLocal() as session:
            task_keys, deleted = await _clear_task_redis_keys(session, redis)
        print()
        if task_keys:
            print(f'Удалено ключей: {deleted} (из {len(task_keys)} задач)')
        else:
            print('Нет ключей для удаления')
    finally:
        await redis_client.close()


async def _clear_task_redis_keys(session, redis) -> tuple[list[str], int]:
    """Удаляет ключи дедупликации BP-1, привязанные к существующим задачам.

    Не сканирует Redis целиком (``KEYS *`` блокирует инстанс и не отличает
    наши числовые ключи от чужих) — берёт список реальных ``SearchTask.id``
    из БД и удаляет ровно соответствующие им ключи.

    Returns:
        ``(candidate_keys, deleted_count)`` — ключи существующих задач и
        сколько из них действительно было в Redis.
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


# ============================================================================
# РАЗБОР АРГУМЕНТОВ
# ============================================================================


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    """Общие параметры прогона для команд сбора."""
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Показывать окно браузера (отладка браузерных стратегий)',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=None,
        help='Таймаут парсинга, мс (по умолчанию из настроек)',
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=None,
        help='Параллельных задач (по умолчанию из настроек)',
    )


def build_parser() -> argparse.ArgumentParser:
    """Строит парсер аргументов CLI."""
    parser = argparse.ArgumentParser(
        prog='bp1',
        description='BP-1: сбор данных из внешних источников',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python -m src.bp1.cli source lenta.ru
  python -m src.bp1.cli competitor "Сбербанк" --inn 7707083893
  python -m src.bp1.cli source-competitor lenta.ru "Сбербанк"
  python -m src.bp1.cli all
  python -m src.bp1.cli add-source https://www.lenta.ru/news
        """,
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # 1. Сбор по источнику.
    source_parser = subparsers.add_parser(
        'source', help='Собрать один источник по всем активным конкурентам'
    )
    source_parser.add_argument(
        'source', help='Источник (lenta.ru | https://lenta.ru/)'
    )
    _add_run_options(source_parser)
    source_parser.set_defaults(func=_cmd_source)

    # 2. Сбор по конкуренту.
    competitor_parser = subparsers.add_parser(
        'competitor',
        help='Собрать одного конкурента по всем активным источникам '
        '(создаётся, если его нет в БД)',
    )
    competitor_parser.add_argument(
        'competitor', help='Название компании (например, Сбербанк)'
    )
    competitor_parser.add_argument(
        '--inn',
        default=None,
        help='ИНН — нужен для поиска по гос. реестрам (fedresurs и др.)',
    )
    _add_run_options(competitor_parser)
    competitor_parser.set_defaults(func=_cmd_competitor)

    # 2.5. Сбор по конкретной паре источник + конкурент.
    source_competitor_parser = subparsers.add_parser(
        'source-competitor',
        help='Собрать ровно одну пару источник + конкурент '
        '(без обхода всей матрицы связок)',
    )
    source_competitor_parser.add_argument(
        'source', help='Источник (lenta.ru | https://lenta.ru/)'
    )
    source_competitor_parser.add_argument(
        'competitor', help='Название компании (например, Сбербанк)'
    )
    source_competitor_parser.add_argument(
        '--inn',
        default=None,
        help='ИНН — нужен для поиска по гос. реестрам (fedresurs и др.)',
    )
    source_competitor_parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Показывать окно браузера (отладка браузерных стратегий)',
    )
    source_competitor_parser.add_argument(
        '--timeout',
        type=int,
        default=None,
        help='Таймаут парсинга, мс (по умолчанию из настроек)',
    )
    source_competitor_parser.set_defaults(func=_cmd_source_competitor)

    # 3. Полный прогон.
    all_parser = subparsers.add_parser(
        'all', help='Полный прогон: все источники x все конкуренты'
    )
    all_parser.add_argument(
        '--no-ensure-matrix',
        action='store_true',
        help='Не создавать недостающие связки — пройти только заведённые',
    )
    _add_run_options(all_parser)
    all_parser.set_defaults(func=_cmd_all)

    # 4. Новый источник.
    add_source_parser = subparsers.add_parser(
        'add-source',
        help='Поставить новый источник на учёт (категоризация + БД + кэш)',
    )
    add_source_parser.add_argument('url', help='Ссылка на источник')
    add_source_parser.set_defaults(func=_cmd_add_source)

    # --- Диагностика ---

    list_parser = subparsers.add_parser(
        'list', help='Показать активные связки источник-конкурент'
    )
    list_parser.set_defaults(func=_cmd_list)

    classify_parser = subparsers.add_parser(
        'classify', help='Категоризировать источник без записи в БД'
    )
    classify_parser.add_argument('source', help='Источник')
    classify_parser.set_defaults(func=_cmd_classify)

    cache_parser = subparsers.add_parser(
        'cache', help='Кэш адаптера источника (просмотр/сброс)'
    )
    cache_parser.add_argument('source', help='Источник')
    cache_parser.add_argument(
        '--show', action='store_true', help='Показать адаптер (по умолчанию)'
    )
    cache_parser.add_argument(
        '--clear', action='store_true', help='Сбросить адаптер'
    )
    cache_parser.set_defaults(func=_cmd_cache)

    quality_parser = subparsers.add_parser(
        'quality', help='Последний собранный RawItem по задаче'
    )
    quality_parser.add_argument('--task-id', type=int, required=True)
    quality_parser.set_defaults(func=_cmd_quality)

    clear_redis_parser = subparsers.add_parser(
        'clear-redis', help='Очистить ключи дедупликации BP-1 в Redis'
    )
    clear_redis_parser.set_defaults(func=_cmd_clear_redis)

    return parser


def main() -> None:
    """Точка входа CLI."""
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == '__main__':
    main()
