"""Конвейер BP-6: витрина → перенос задач LLM в план действий (action_item).

Берёт П1/П2-события витрины (showcase_event), у которых есть связанное
размеченное событие (categorized_event) с непустым списком задач
(`task`, сформирован LLM на BP-3, GenerationTaskModule), и заводит по
одной строке `action_item` на каждую задачу — отдел копируется из
categorized_event.department_id, конкретный исполнитель (assigned_user_id)
не назначается, это решает человек.

Порядок шагов:

  1. отобрать П1/П2-события без action_items_generated_at —
    select_pending_events (crud)
  2. на каждую задачу из categorized_event.task — одна строка action_item —
    build_action_item_rows
  3. записать пачкой — insert_action_items (crud)
  4. пометить ВСЕ рассмотренные события — mark_generated (crud),
    независимо от результата

Идемпотентность: событие обрабатывается один раз (watermark
`action_items_generated_at IS NULL`, БЕЗ реакции на updated_at) — если
categorized_event.task позже поменяется при перекатегоризации, уже
заведённые action_item не переписываются и не дублируются (сознательное
решение первой версии, см. design.md).
"""

from datetime import UTC, datetime

from core.database import AsyncSessionLocal
from src.bp4.models import ShowcaseEvent
from src.bp6.crud import Bp6Crud


def build_action_item_rows(events: list[ShowcaseEvent]) -> list[dict]:
    """Разложить task[] каждого события в отдельные строки action_item.

    Пропускает событие целиком, если department_id у связанного
    categorized_event не резолвлен (NULL) — ActionItem.department_id
    NOT NULL, а LLM мог не подобрать отдел; такое событие остаётся без
    автозадач (watermark всё равно проставится в run_bp6).
    """
    rows: list[dict] = []
    for event in events:
        ce = event.categorized_event
        tasks = ce.task if ce else None
        if not tasks or ce.department_id is None:
            continue
        for task_text in tasks:
            rows.append(
                {
                    'showcase_event_id': event.id,
                    'task': task_text,
                    'department_id': ce.department_id,
                    'assigned_user_id': None,
                    'deadline': ce.deadline,
                    'expected_result': ce.expected_result,
                }
            )
    return rows


async def run_bp6() -> dict:
    """Один прогон конвейера BP-6: витрина -> action_item.

    Возвращает сводку прогона: сколько П1/П2-событий рассмотрено, сколько
    из них дали хотя бы одну задачу, сколько строк action_item создано.
    """
    async with AsyncSessionLocal() as session:
        crud = Bp6Crud(session)
        generated_at = datetime.now(UTC)

        events = await crud.select_pending_events()
        rows = build_action_item_rows(events)

        await crud.insert_action_items(rows)
        await crud.mark_generated([event.id for event in events], generated_at)
        await session.commit()

        events_with_tasks = sum(
            1 for event in events if event.categorized_event.task
        )
        return {
            'events_considered': len(events),
            'events_with_tasks': events_with_tasks,
            'action_items_created': len(rows),
        }


if __name__ == '__main__':
    import asyncio

    print(asyncio.run(run_bp6()))
