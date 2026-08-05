"""Скрипт миграции существующих raw-файлов к эталонной структуре JSONB.

Что делает:
1. Рекурсивно находит все *.json файлы в data/raw/
2. Для каждого файла:
   - Переименовывает date -> published_at
   - Переименовывает media -> media_name
   - Оборачивает salary -> extra: {"salary": value}
   - Удаляет meta.status
   - Очищает meta.source от протокола (https://... -> имя)
3. Работает в двух режимах: --dry-run (только показать) и --execute (записать)

Запуск:
    python -m core.scripts.migrate_raw_files --dry-run
    python -m core.scripts.migrate_raw_files
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# Корень данных относительно kodik/
RAW_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / 'data' / 'raw'

# Паттерн для очистки source от протокола
_SOURCE_CLEANUP = re.compile(r'^https?://(?:www\.)?([^/]+).*$')


def _clean_source(source: str) -> str:
    """Очистить source от протокола: URL -> домен."""
    m = _SOURCE_CLEANUP.match(source)
    if m:
        return m.group(1)
    return source


def _migrate_item(item: dict) -> dict:
    """Сконвертировать один item из старого формата в новый."""
    new_item = {}

    # url, title, text — без изменений
    for key in ('url', 'title', 'text'):
        if key in item:
            new_item[key] = item[key]

    # date -> published_at
    new_item['published_at'] = item.get('date')

    # region — без изменений
    new_item['region'] = item.get('region')

    # media -> media_name
    new_item['media_name'] = item.get('media')

    # salary -> extra: {"salary": ...}
    salary = item.get('salary')
    new_item['extra'] = {'salary': salary} if salary is not None else {}

    return new_item


def _migrate_meta(meta: dict) -> dict:
    """Сконвертировать meta из старого формата в новый (удалить status)."""
    new_meta = {}
    for key in (
        'search_task_id',
        'source',
        'competitor',
        'trigger',
        'source_request_url',
        'fetched_at',
    ):
        if key in meta:
            new_meta[key] = meta[key]

    # Очищаем source от протокола
    if 'source' in new_meta:
        new_meta['source'] = _clean_source(new_meta['source'])

    return new_meta


def migrate_file(filepath: Path, dry_run: bool = False) -> bool:
    """Мигрировать один файл. Возвращает True, если были изменения."""
    try:
        with open(filepath, encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error('Ошибка чтения %s: %s', filepath, e)
        return False

    old_json = json.dumps(data, ensure_ascii=False, indent=2)

    # Мигрируем meta
    if 'meta' in data:
        data['meta'] = _migrate_meta(data['meta'])

    # Мигрируем items
    if 'items' in data and isinstance(data['items'], list):
        data['items'] = [_migrate_item(item) for item in data['items']]

    new_json = json.dumps(data, ensure_ascii=False, indent=2)

    if old_json == new_json:
        return False

    if dry_run:
        logger.info('[DRY-RUN] Будет изменён: %s', filepath)
    else:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_json)
            logger.info('Мигрирован: %s', filepath)
        except OSError as e:
            logger.error('Ошибка записи %s: %s', filepath, e)
            return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Миграция raw-файлов к эталонной структуре JSONB',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Только показать, какие файлы будут изменены (без записи)',
    )
    args = parser.parse_args()

    if not RAW_DATA_ROOT.is_dir():
        logger.error('Директория не найдена: %s', RAW_DATA_ROOT)
        sys.exit(1)

    json_files = sorted(RAW_DATA_ROOT.rglob('*.json'))
    if not json_files:
        logger.info('JSON-файлы не найдены в %s', RAW_DATA_ROOT)
        return

    logger.info(
        'Найдено %d файлов. Режим: %s',
        len(json_files),
        'DRY-RUN' if args.dry_run else 'EXECUTE',
    )

    changed = 0
    for fp in json_files:
        if migrate_file(fp, dry_run=args.dry_run):
            changed += 1

    logger.info('Готово. Изменено файлов: %d', changed)


if __name__ == '__main__':
    main()
