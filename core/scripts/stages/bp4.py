"""Этап BP-4: витрина (showcase_event).

Единственный этап, который НИЧЕГО не подделывает: витрину незачем сочинять,
её собирает готовый конвейер из фактов и разметки. Модуль существует ради
симметрии команд (у каждого БП свой скрипт) и ради clear().

Запуск:
    python -m core.scripts.stages.bp4

То же самое, но со своей транзакцией — прямой вызов конвейера:
    python -c "import asyncio; from src.bp4.pipeline import run_bp4; \\
               print(asyncio.run(run_bp4()))"

Требует залитой разметки (stages/bp3). Инкрементален: повторный запуск
без clear ничего не продублирует, а переразмеченные события обновит.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from core.scripts.stages.cascade import clear_from
from src.bp4.models import ShowcaseEvent
from src.bp4.pipeline import sync_showcase


async def seed(session: AsyncSession) -> int:
    """Собрать витрину настоящим конвейером BP-4."""
    summary = await sync_showcase(session)
    await session.flush()
    return summary['upserted']


async def clear(session: AsyncSession) -> int:
    """Снести витрину и всё, что на ней построено (алерты, задачи)."""
    return await clear_from(session, ShowcaseEvent)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-4 (витрина)', clear, seed)
