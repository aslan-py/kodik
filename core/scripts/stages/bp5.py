"""Этап BP-5: журнал алертов (alert).

Единственный этап, который НИЧЕГО не подделывает (как bp4): детектор
незачем имитировать вручную, его запускает готовый конвейер BP-5. Модуль
существует ради симметрии команд и ради clear().

Запуск:
    python -m core.scripts.stages.bp5

То же самое, но со своей транзакцией — прямой вызов конвейера:
    python -c "import asyncio; from src.bp5.pipeline import run_bp5; \\
               print(asyncio.run(run_bp5()))"

Требует залитой витрины (stages/bp4) и справочников BP-5 (event_type,
channel, user, routing_rule). Инкрементален: повторный запуск без clear
ничего не продублирует.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from core.scripts.stages.cascade import clear_from
from src.bp4.models import ShowcaseEvent
from src.bp5.models import Alert
from src.bp5.pipeline import sync_alerts


async def seed(session: AsyncSession) -> int:
    """Прогнать витрину через детектор настоящим конвейером BP-5."""
    summary = await sync_alerts(session)
    await session.flush()
    return summary['alerts']


async def clear(session: AsyncSession) -> int:
    """Снести журнал алертов и сбросить watermark на витрине.

    clear_from(Alert) удаляет alert/action_item, но НЕ трогает
    showcase_event — та таблица выше по PIPELINE_ORDER, её строки
    переживают эту очистку. Значит alerted_at остался бы проставленным
    с прошлого прогона, и повторный seed() не нашёл бы что перепроверять
    (критерий отбора: alerted_at IS NULL OR updated_at > alerted_at).
    Сбрасываем watermark явно.

    updated_at перезаписываем его же значением (self-reference), чтобы
    НЕ дать сработать onupdate этого поля — иначе bulk UPDATE без
    указанного updated_at в .values() сдвинул бы его на текущий момент
    (onupdate срабатывает на любом UPDATE через SQLAlchemy, не только на
    точечной ORM-правке), и витрина выглядела бы «пересобранной», хотя
    её содержимое не менялось.
    """
    total = await clear_from(session, Alert)
    await session.execute(
        ShowcaseEvent.__table__.update().values(
            alerted_at=None,
            updated_at=ShowcaseEvent.updated_at,
        )
    )
    return total


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-5 (алерты)', clear, seed)
