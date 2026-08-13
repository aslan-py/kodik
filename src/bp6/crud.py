"""Слой доступа к данным BP-6: отбор событий, запись action_item.

Методы (по потоку конвейера):
    select_pending_events → П1/П2-события витрины, ещё не обработанные BP-6
    insert_action_items   → запись пачки action_item (обычный INSERT —
                             у ActionItem нет natural UNIQUE, идемпотентность
                             держит watermark, не ON CONFLICT)
    mark_generated         → проставить action_items_generated_at (событие
                              обработано, независимо от результата)

Сессия — в self.session (через __init__), методы её не принимают. Транзакцией
(commit/rollback) управляет вызывающий код — здесь только запросы.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.enums import PriorityLevel
from src.bp4.constants import PRIORITY_DISPLAY
from src.bp4.models import ShowcaseEvent
from src.bp6.models import ActionItem


class Bp6Crud:
    """Репозиторий BP-6: отбор витрины, запись плана действий."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def select_pending_events(self) -> Sequence[ShowcaseEvent]:
        """П1/П2-события витрины, ещё не обработанные BP-6.

        Только `action_items_generated_at IS NULL` — БЕЗ реакции на
        `updated_at` (в отличие от `alerted_at` в BP-5): изменение задач
        при перекатегоризации уже обработанного события сознательно не
        перезапускает перенос (см. design.md, Decisions). Подгружает
        связанный `categorized_event` (task/expected_result/department_id)
        одним запросом — избегаем N+1 при переборе событий.
        """
        priorities = (
            PRIORITY_DISPLAY[PriorityLevel.p1],
            PRIORITY_DISPLAY[PriorityLevel.p2],
        )
        stmt = (
            select(ShowcaseEvent)
            .where(
                ShowcaseEvent.priority.in_(priorities),
                ShowcaseEvent.action_items_generated_at.is_(None),
            )
            .options(selectinload(ShowcaseEvent.categorized_event))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def insert_action_items(self, rows: Sequence[dict]) -> None:
        """Записать пачку `action_item` — по одной строке на задачу.

        Обычный INSERT: у `ActionItem` нет natural UNIQUE на
        (showcase_event_id, task) — задваивание предотвращает watermark на
        `showcase_event`, не ON CONFLICT здесь.
        """
        if not rows:
            return
        await self.session.execute(ActionItem.__table__.insert(), list(rows))

    async def mark_generated(
        self, event_ids: Sequence[int], generated_at: datetime
    ) -> None:
        """Проставить `action_items_generated_at` пачке событий —
        независимо от того, создались ли для них строки `action_item`.

        `updated_at` явно перезаписываем его же значением (self-reference),
        чтобы bulk UPDATE не сдвинул его через `onupdate` — иначе критерий
        BP-5 (`updated_at > alerted_at`) мог бы ложно счесть событие
        изменившимся и повторно проверить его на алертинг без причины
        (тот же приём, что `mark_checked` в `src/bp5/crud.py`).
        """
        if not event_ids:
            return
        await self.session.execute(
            ShowcaseEvent.__table__.update()
            .where(ShowcaseEvent.id.in_(event_ids))
            .values(
                action_items_generated_at=generated_at,
                updated_at=ShowcaseEvent.updated_at,
            )
        )
