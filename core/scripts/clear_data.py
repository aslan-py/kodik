"""Очистка ДАННЫХ пайплайна (справочники остаются).

Пара к seed_all: типовой цикл теста — один раз seed_all, поработал, затем
clear_data → seed_all, чтобы вернуть данные в исходное состояние без
пересоздания БД.

Чистит таблицы-данные в порядке, обратном FK-зависимостям:
    action_item → alert → showcase_event → categorized_event →
    normalized_item → raw_item → search_task

Справочники (region, competitor, source, trigger, black_domain, stop_word,
topic_limit, category, department, event_type, channel, routing_rule) НЕ
трогаем — они наполняются один раз и правятся руками при необходимости.
Схему и enum-типы не трогаем (этим управляет Alembic).

Запуск (из любого места):
    python -m core.scripts.clear_data
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from src.bp1.models import RawItem, SearchTask  # noqa: E402
from src.bp2.models import NormalizedItem  # noqa: E402
from src.bp3.models import CategorizedEvent  # noqa: E402
from src.bp4.models import ShowcaseEvent  # noqa: E402
from src.bp5.models import Alert  # noqa: E402
from src.bp6.models import ActionItem  # noqa: E402

# Порядок = обратный FK-зависимостям (сначала «дети», потом «родители»).
MODELS = [
    ActionItem,
    Alert,
    ShowcaseEvent,
    CategorizedEvent,
    NormalizedItem,
    RawItem,
    SearchTask,
]


async def clear() -> None:
    async with AsyncSessionLocal() as session:
        for model in MODELS:
            result = await session.execute(delete(model))
            print(f'{model.__tablename__:18} удалено {result.rowcount} строк')
        await session.commit()
    print('Данные пайплайна очищены (справочники сохранены).')


if __name__ == '__main__':
    asyncio.run(clear())
