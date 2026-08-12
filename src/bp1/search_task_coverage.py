"""Автоматическое заполнение покрытия задачами сбора BP-1.

Синхронизация создаёт недостающие задачи без поискового слова для всех
активных пар «конкурент × источник». Она только досоздаёт строки: не удаляет
и не деактивирует существующие задачи, не меняет их ``is_active`` и не
создаёт задачи с поисковым словом. Поэтому ручное исключение пары хранится
как неактивная задача и переживает повторные синхронизации.
"""

import asyncio
import json

from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from src.bp1.models import Competitor, SearchTask, Source


async def sync_search_task_coverage(session: AsyncSession) -> int:
    """Досоздать задачи по всем активным парам и вернуть их число.

    Все пары отправляются в Postgres одной операцией ``INSERT ... SELECT``.
    Существующие ограничения ``search_task`` и ``ON CONFLICT DO NOTHING``
    обеспечивают идемпотентность, включая параллельные запуски. Коммит
    остаётся ответственностью вызывающего кода.
    """
    active_pairs = (
        select(
            Competitor.id.label('competitor_id'),
            Source.id.label('source_id'),
            literal(None).label('trigger_id'),
        )
        .select_from(Competitor)
        .join(Source, literal(True))
        .where(Competitor.is_active.is_(True), Source.is_active.is_(True))
    )
    statement = (
        pg_insert(SearchTask)
        .from_select(['competitor_id', 'source_id', 'trigger_id'], active_pairs)
        .on_conflict_do_nothing()
        .returning(SearchTask.id)
    )
    result = await session.execute(statement)
    return len(result.scalars().all())


async def run_search_task_coverage() -> dict[str, int]:
    """Синхронизировать покрытие в своей транзакции, не запуская сбор."""
    async with AsyncSessionLocal() as session:
        created = await sync_search_task_coverage(session)
        await session.commit()
    return {'search_tasks_created': created}


def main() -> None:
    """CLI для дешёвой синхронизации покрытия без Redis и внешней сети."""
    result = asyncio.run(run_search_task_coverage())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
