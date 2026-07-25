"""Скрипт ручного пересева таблицы region из src\bp2\files\\cities.json

Используется когда нужно обновить данные без отката миграции:
добавили города в JSON → запустили скрипт → таблица обновлена.

Идемпотентен: повторный запуск обновляет существующие записи
(ON CONFLICT DO UPDATE), не плодит дублей.

Запуск (из любого места):
    python src/bp2/scripts/seed_regions.py
    python -m src.bp2.scripts.seed_regions
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы скрипт работал при запуске
# как напрямую (python seed_regions.py), так и через кнопку Run в VS Code.
PROJECT_ROOT = Path(__file__).parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from src.bp2.models import Region  # noqa: E402

CITIES_FILE = Path(__file__).parents[1] / 'files' / 'cities.json'


def make_aliases(name: str) -> list[str]:
    """Генерирует стандартные псевдонимы из канонического имени города."""
    n = name.lower()
    return list(dict.fromkeys([n, f'г. {n}', f'г {n}']))


async def seed() -> None:
    with open(CITIES_FILE, encoding='utf-8') as f:
        cities = json.load(f)

    seen: set[str] = set()
    rows = []
    for city in cities:
        name = city['name']
        if name in seen:
            continue
        seen.add(name)
        coords = city.get('coords') or {}
        lat = coords.get('lat')
        lon = coords.get('lon')
        json_aliases: list[str] = city.get('aliases', [])
        merged = list(dict.fromkeys(json_aliases + make_aliases(name)))
        rows.append(
            {
                'name_display': name,
                'name_aliases': merged,
                'macro_region': city.get('district'),
                'latitude': float(lat) if lat else None,
                'longitude': float(lon) if lon else None,
            }
        )

    async with AsyncSessionLocal() as session:
        stmt = insert(Region).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=['name_display'],
            set_={
                'name_aliases': stmt.excluded.name_aliases,
                'macro_region': stmt.excluded.macro_region,
                'latitude': stmt.excluded.latitude,
                'longitude': stmt.excluded.longitude,
            },
        )
        await session.execute(stmt)
        await session.commit()

    print(f'Seeded {len(rows)} regions from {CITIES_FILE.name}')


if __name__ == '__main__':
    asyncio.run(seed())
