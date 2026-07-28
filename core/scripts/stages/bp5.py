"""Этап BP-5: журнал алертов (alert).

Имитирует детектор значимых событий: пробегает витрину, ищет в заголовках
слова-маркеры из event_type.keywords и по паре (тип, приоритет) достаёт
маршрут из routing_rule. Одно правило = одна доставка, поэтому у события
может быть несколько строк алерта (telegram + email).

Запуск:
    python -m core.scripts.stages.bp5

Статус проставляется по режиму доставки: instant → сразу sent (доставили),
digest → queued (ждёт джобу-сводку). Это ровно то состояние, в котором
журнал оказался бы после реального прогона.

Требует залитой витрины (stages/bp4) и справочников BP-5.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AlertStatus, DeliveryMode, PriorityLevel
from core.scripts.stages.cascade import clear_from
from src.bp4.constants import PRIORITY_FROM_DISPLAY
from src.bp4.models import ShowcaseEvent
from src.bp5.models import Alert, EventType, RoutingRule


async def seed(session: AsyncSession) -> int:
    """Прогнать витрину через детектор и записать журнал доставок."""
    # keywords хранятся строкой через запятую — разбираем в список один раз.
    event_types = [
        (row.id, [kw.strip().lower() for kw in row.keywords.split(',')])
        for row in (await session.execute(select(EventType))).scalars()
    ]
    routes: dict[tuple[int, PriorityLevel], list[RoutingRule]] = {}
    for rule in (await session.execute(select(RoutingRule))).scalars():
        routes.setdefault((rule.event_type_id, rule.priority), []).append(rule)

    events = (await session.execute(select(ShowcaseEvent))).scalars()
    now = datetime.now(UTC)
    added = 0
    for event in events:
        title = (event.title or '').lower()
        priority = PRIORITY_FROM_DISPLAY.get(event.priority)
        if priority is None:
            continue
        matched = next(
            (
                type_id
                for type_id, keywords in event_types
                if any(kw in title for kw in keywords)
            ),
            None,
        )
        if matched is None:
            continue  # незначимое событие — алерта нет
        for rule in routes.get((matched, priority), []):
            delivered = rule.mode == DeliveryMode.instant
            session.add(
                Alert(
                    showcase_event_id=event.id,
                    event_type_id=matched,
                    priority=priority,
                    department_id=rule.department_id,
                    channel_id=rule.channel_id,
                    mode=rule.mode,
                    status=AlertStatus.sent
                    if delivered
                    else AlertStatus.queued,
                    sent_at=now if delivered else None,
                )
            )
            added += 1

    await session.flush()
    return added


async def clear(session: AsyncSession) -> int:
    """Снести журнал алертов (и задачи, которые ниже по потоку)."""
    return await clear_from(session, Alert)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-5 (алерты)', clear, seed)
