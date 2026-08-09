#!/usr/bin/env python3
"""CLI-скрипт заполнения БД данными BP-1 из CSV-файлов.

Заполняет таблицы: Competitor, Trigger, Source, SearchTask.
Поддерживает идемпотентность (ON CONFLICT DO NOTHING) и dry-run режим.

Расположение: core/seed_data.py (вместе с конфигом и database.py).
CSV-файлы лежат рядом: core/data/*.csv.

Запуск (из корня проекта):
    python -m core.scripts.seed_data                     # полный прогон из CSV
    python -m core.scripts.seed_data --dry-run     # показать что будет сделано
    python -m core.scripts.seed_data --only competitors     # только конкуренты
    python -m core.scripts.seed_data --clear      # очистить и заполнить заново
    python -m core.scripts.seed_data --csv-dir ./custom/path  # свой путь к CSV

Или напрямую:
    python core/seed_data.py

Повторный запуск безопасен — дубликаты не создаются (ON CONFLICT DO NOTHING).
"""

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from src.bp1.models import Competitor, RawItem, SearchTask, Source, Trigger

# Добавляем корень проекта в PYTHONPATH для импорта моделей
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)

# Путь к CSV-файлам по умолчанию (рядом со скриптом, в подпапке data/)
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


# ──────────────────────────── Модели данных ────────────────────────────


@dataclass
class CompetitorRow:
    """Строка из competitor.csv."""

    name: str
    inn: str | None


@dataclass
class SourceRow:
    """Строка из source.csv."""

    name: str


@dataclass
class TriggerRow:
    """Строка из trigger.csv."""

    keyword: str


@dataclass
class SearchTaskRow:
    """Строка из search_task.csv (имена вместо ID)."""

    competitor_name: str
    source_name: str
    trigger_keyword: str | None


# ──────────────────────────── Чтение CSV ──────────────────────────────


def read_competitors_csv(path: Path) -> list[CompetitorRow]:
    """Читает competitor.csv → список CompetitorRow.

    Пустой inn преобразуется в None (а не пустую строку).
    """
    rows: list[CompetitorRow] = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            name = row['name'].strip()
            if not name:
                log.warning('competitor.csv:%d — пустое name, пропуск', line_no)
                continue
            inn_raw = row.get('inn', '').strip()
            inn = inn_raw if inn_raw else None
            rows.append(CompetitorRow(name=name, inn=inn))
    return rows


def read_sources_csv(path: Path) -> list[SourceRow]:
    """Читает source.csv → список SourceRow."""
    rows: list[SourceRow] = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            name = row['name'].strip()
            if not name:
                log.warning('source.csv:%d — пустое name, пропуск', line_no)
                continue
            rows.append(SourceRow(name=name))
    return rows


def read_triggers_csv(path: Path) -> list[TriggerRow]:
    """Читает trigger.csv → список TriggerRow."""
    rows: list[TriggerRow] = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            keyword = row['keyword'].strip()
            if not keyword:
                log.warning('trigger.csv:%d — пустое keyword, пропуск', line_no)
                continue
            rows.append(TriggerRow(keyword=keyword))
    return rows


def read_search_tasks_csv(path: Path) -> list[SearchTaskRow]:
    """Читает search_task.csv → список SearchTaskRow.

    trigger_keyword может быть пустым — тогда trigger_id будет NULL.
    """
    rows: list[SearchTaskRow] = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for line_no, row in enumerate(reader, start=2):
            comp = row['competitor_name'].strip()
            src = row['source_name'].strip()
            if not comp or not src:
                log.warning(
                    'search_task.csv:%d — пустое имя конкурента или '
                    'источника, пропуск',
                    line_no,
                )
                continue
            trig_raw = (row.get('trigger_keyword') or '').strip()
            trig = trig_raw if trig_raw else None
            rows.append(
                SearchTaskRow(
                    competitor_name=comp,
                    source_name=src,
                    trigger_keyword=trig,
                )
            )
    return rows


# ──────────────────────────── Вставка данных ───────────────────────────


async def insert_competitors(
    session: AsyncSession,
    rows: list[CompetitorRow],
    dry_run: bool,
) -> int:
    """Вставляет конкурентов. Возвращает количество добавленных."""
    added = 0
    for row in rows:
        # Проверяем существование по unique name
        existing = await session.execute(
            select(Competitor).where(Competitor.name == row.name)
        )
        if existing.scalar_one_or_none():
            log.info("Конкурент '%s' уже существует, пропуск", row.name)
            continue

        if dry_run:
            log.info('[DRY-RUN] Конкурент: %s (ИНН=%s)', row.name, row.inn)
            added += 1
            continue

        obj = Competitor(name=row.name, inn=row.inn)
        session.add(obj)
        try:
            await session.flush()
            log.info("Конкурент '%s' добавлен (id=%d)", row.name, obj.id)
            added += 1
        except IntegrityError:
            await session.rollback()
            log.warning(
                "Конкурент '%s' — дубликат (race condition), пропуск",
                row.name,
            )
    return added


async def insert_sources(
    session: AsyncSession,
    rows: list[SourceRow],
    dry_run: bool,
) -> int:
    """Вставляет источники. Возвращает количество добавленных."""
    added = 0
    for row in rows:
        existing = await session.execute(
            select(Source).where(Source.name == row.name)
        )
        if existing.scalar_one_or_none():
            log.info("Источник '%s' уже существует, пропуск", row.name)
            continue

        if dry_run:
            log.info('[DRY-RUN] Источник: %s', row.name)
            added += 1
            continue

        obj = Source(name=row.name)
        session.add(obj)
        try:
            await session.flush()
            log.info("Источник '%s' добавлен (id=%d)", row.name, obj.id)
            added += 1
        except IntegrityError:
            await session.rollback()
            log.warning(
                "Источник '%s' — дубликат (race condition), пропуск",
                row.name,
            )
    return added


async def insert_triggers(
    session: AsyncSession,
    rows: list[TriggerRow],
    dry_run: bool,
) -> int:
    """Вставляет триггеры. Возвращает количество добавленных."""
    added = 0
    for row in rows:
        existing = await session.execute(
            select(Trigger).where(Trigger.keyword == row.keyword)
        )
        if existing.scalar_one_or_none():
            log.info("Триггер '%s' уже существует, пропуск", row.keyword)
            continue

        if dry_run:
            log.info('[DRY-RUN] Триггер: %s', row.keyword)
            added += 1
            continue

        obj = Trigger(keyword=row.keyword)
        session.add(obj)
        try:
            await session.flush()
            log.info("Триггер '%s' добавлен (id=%d)", row.keyword, obj.id)
            added += 1
        except IntegrityError:
            await session.rollback()
            log.warning(
                "Триггер '%s' — дубликат (race condition), пропуск",
                row.keyword,
            )
    return added


async def insert_search_tasks(
    session: AsyncSession,
    rows: list[SearchTaskRow],
    dry_run: bool,
) -> int:
    """Вставляет матрицу задач (search_task).

    Ищет конкурентов, источники и триггеры по unique полям (name/keyword).
    Если запись не найдена — пропуск с логом ошибки.
    """
    added = 0
    for row in rows:
        # Находим конкурента по name
        comp_result = await session.execute(
            select(Competitor).where(Competitor.name == row.competitor_name)
        )
        competitor = comp_result.scalar_one_or_none()
        if not competitor:
            log.error(
                "Конкурент '%s' не найден, пропуск search_task",
                row.competitor_name,
            )
            continue

        # Находим источник по name
        src_result = await session.execute(
            select(Source).where(Source.name == row.source_name)
        )
        source = src_result.scalar_one_or_none()
        if not source:
            log.error(
                "Источник '%s' не найден, пропуск search_task",
                row.source_name,
            )
            continue

        # Находим триггер по keyword (может быть NULL)
        trigger_id = None
        if row.trigger_keyword:
            trig_result = await session.execute(
                select(Trigger).where(Trigger.keyword == row.trigger_keyword)
            )
            trigger = trig_result.scalar_one_or_none()
            if not trigger:
                log.error(
                    "Триггер '%s' не найден, пропуск search_task",
                    row.trigger_keyword,
                )
                continue
            trigger_id = trigger.id

        # Проверяем уникальность (competitor_id, source_id, trigger_id)
        existing = await session.execute(
            select(SearchTask).where(
                SearchTask.competitor_id == competitor.id,
                SearchTask.source_id == source.id,
                SearchTask.trigger_id == trigger_id,
            )
        )
        if existing.scalar_one_or_none():
            log.info(
                'SearchTask (%s × %s × %s) уже существует, пропуск',
                row.competitor_name,
                row.source_name,
                row.trigger_keyword or 'NULL',
            )
            continue

        if dry_run:
            log.info(
                '[DRY-RUN] SearchTask: %s × %s × %s',
                row.competitor_name,
                row.source_name,
                row.trigger_keyword or 'NULL',
            )
            added += 1
            continue

        obj = SearchTask(
            competitor_id=competitor.id,
            source_id=source.id,
            trigger_id=trigger_id,
        )
        session.add(obj)
        try:
            await session.flush()
            log.info(
                'SearchTask добавлен (id=%d): %s × %s × %s',
                obj.id,
                row.competitor_name,
                row.source_name,
                row.trigger_keyword or 'NULL',
            )
            added += 1
        except IntegrityError:
            await session.rollback()
            log.warning(
                'SearchTask (%s × %s × %s) — дубликат, пропуск',
                row.competitor_name,
                row.source_name,
                row.trigger_keyword or 'NULL',
            )
    return added


# ──────────────────────────── Очистка ──────────────────────────────────


async def clear_tables(session: AsyncSession) -> None:
    """Очищает таблицы в правильном порядке (с учётом FK).

    Порядок: raw_item → search_task → trigger → source → competitor.
    """
    log.info('Очистка таблиц...')
    await session.execute(delete(RawItem))
    await session.execute(delete(SearchTask))
    await session.execute(delete(Trigger))
    await session.execute(delete(Source))
    await session.execute(delete(Competitor))
    await session.flush()
    log.info('Таблицы очищены')


# ──────────────────────────── Главная функция ──────────────────────────


async def seed(
    data_dir: Path,
    only: str | None = None,
    dry_run: bool = False,
    clear: bool = False,
) -> None:
    """Основная функция заполнения БД.

    Args:
        data_dir: папка с CSV-файлами
        only: тип данных для импорта (competitors/sources/triggers/tasks)
        dry_run: если True — только показать что будет сделано
        clear: если True — очистить таблицы перед вставкой
    """
    # Проверяем existence CSV-файлов
    csv_files = {
        'competitors': data_dir / 'competitor.csv',
        'sources': data_dir / 'source.csv',
        'triggers': data_dir / 'trigger.csv',
        'tasks': data_dir / 'search_task.csv',
    }

    for _name, path in csv_files.items():
        if not path.exists():
            log.error('CSV-файл не найден: %s', path)
            sys.exit(1)

    # Определяем что заполнять
    if only:
        if only not in csv_files:
            log.error(
                "Неизвестный тип '%s'. Допустимые: %s",
                only,
                ', '.join(csv_files.keys()),
            )
            sys.exit(1)
        run_types = {only}
    else:
        run_types = set(csv_files.keys())

    log.info(
        'Режим: %s | Типы: %s | CSV: %s',
        'DRY-RUN' if dry_run else 'RECORD',
        ', '.join(sorted(run_types)),
        data_dir,
    )

    # Читаем CSV
    competitors = read_competitors_csv(csv_files['competitors'])
    sources = read_sources_csv(csv_files['sources'])
    triggers = read_triggers_csv(csv_files['triggers'])
    search_tasks = read_search_tasks_csv(csv_files['tasks'])

    log.info(
        'Из CSV прочитано: %d конкурентов, %d источников, '
        '%d триггеров, %d задач',
        len(competitors),
        len(sources),
        len(triggers),
        len(search_tasks),
    )

    # Подключаемся к БД и вставляем
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                if clear and not dry_run:
                    await clear_tables(session)

                stats: dict[str, int] = {}

                if 'competitors' in run_types:
                    stats['Конкуренты'] = await insert_competitors(
                        session,
                        competitors,
                        dry_run,
                    )

                if 'sources' in run_types:
                    stats['Источники'] = await insert_sources(
                        session,
                        sources,
                        dry_run,
                    )

                if 'triggers' in run_types:
                    stats['Триггеры'] = await insert_triggers(
                        session,
                        triggers,
                        dry_run,
                    )

                if 'tasks' in run_types:
                    stats['SearchTask'] = await insert_search_tasks(
                        session,
                        search_tasks,
                        dry_run,
                    )

            # Если dry_run — откатываем (ничего не сохранялось)
            if dry_run:
                await session.rollback()
                log.info('DRY-RUN: транзакция откачена (данные не сохранены)')

            # Выводим итоговую статистику
            log.info('═══ ИТОГО ═══')
            for label, count in stats.items():
                log.info('  %s: %d добавлено', label, count)

        except SQLAlchemyError as e:
            await session.rollback()
            log.error('Ошибка БД: %s', e)
            sys.exit(1)


# ──────────────────────────── CLI ──────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description='Заполнение БД данными BP-1 из CSV-файлов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Примеры:\n'
            '  python -m core.seed_data\n'
            '  python -m core.seed_data --dry-run\n'
            '  python -m core.seed_data --only competitors\n'
            '  python -m core.seed_data --clear\n'
        ),
    )
    parser.add_argument(
        '--csv-dir',
        type=Path,
        default=_DEFAULT_DATA_DIR,
        help='Папка с CSV-файлами (по умолчанию: core/data/)',
    )
    parser.add_argument(
        '--only',
        choices=['competitors', 'sources', 'triggers', 'tasks'],
        help='Импортировать только указанный тип данных',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать что будет сделано, не записывая в БД',
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Очистить таблицы перед вставкой (search_task, trigger, '
        'source, competitor)',
    )
    return parser.parse_args()


def main() -> None:
    """Точка входа CLI."""
    args = parse_args()

    if not args.csv_dir.exists():
        log.error('Папка с CSV не найдена: %s', args.csv_dir)
        sys.exit(1)

    asyncio.run(
        seed(
            data_dir=args.csv_dir,
            only=args.only,
            dry_run=args.dry_run,
            clear=args.clear,
        )
    )


if __name__ == '__main__':
    main()
