"""Этап BP-6: план действий (action_item).

Заводит задачи по событиям приоритета П1 и П2 — тем, на которые ТЗ требует
реакции. В бою задачу ставит человек через админку; здесь заполняем за него,
чтобы дашборд «план действий» было чем наполнить.

Запуск:
    python -m core.scripts.stages.bp6

Задача берёт текст из требуемого действия витрины (его предложила LLM
в BP-3), срок — оттуда же. Статус у всех open: отделы двигают его сами.

Требует залитой витрины (stages/bp4).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import ActionStatus
from core.scripts.stages.cascade import clear_from
from src.bp3.models import Department
from src.bp4.models import ShowcaseEvent
from src.bp6.models import ActionItem

# Приоритеты, по которым заводится задача (подписи витрины, не коды enum).
ACTIONABLE_PRIORITIES = ('П1', 'П2')


async def seed(session: AsyncSession) -> int:
    """Завести задачу по каждому событию П1/П2 с указанным отделом."""
    departments = {
        d.name: d.id
        for d in (await session.execute(select(Department))).scalars()
    }
    events = (
        await session.execute(
            select(ShowcaseEvent).where(
                ShowcaseEvent.priority.in_(ACTIONABLE_PRIORITIES)
            )
        )
    ).scalars()

    added = 0
    for event in events:
        department_id = departments.get(event.department)
        if department_id is None:
            continue  # без ответственного задачу не на кого повесить
        session.add(
            ActionItem(
                showcase_event_id=event.id,
                task=event.action or f'Отработать событие: {event.title}',
                department_id=department_id,
                deadline=event.deadline,
                expected_result=(
                    'Событие отработано, реакция задокументирована'
                ),
                status=ActionStatus.open,
            )
        )
        added += 1

    await session.flush()
    return added


async def clear(session: AsyncSession) -> int:
    """Снести задачи плана действий (это самый нижний слой)."""
    return await clear_from(session, ActionItem)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-6 (план действий)', clear, seed)
