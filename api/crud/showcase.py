"""Репозиторий витрины BP-4 для API: чтение + write-through правка.

Витрина (showcase_event) — производная таблица (ABOUT.md, BP-4 п.5):
источник правды для priority/category/tonality/action/deadline/
department/comment — это categorized_event. Прямой UPDATE showcase_event
разъехался бы с categorized_event молча и был бы затёрт следующим
инкрементом BP-4 (см. FASTAPI_PLAN.md, п.3).

ShowcaseCRUD.update() поэтому пишет ДВАЖДЫ в одной транзакции:
  1. в categorized_event — те же значения, что и правит аналитик (enum'ы
     priority/tonality, id категории/отдела) — источник правды;
  2. зеркалом в showcase_event — переводим в готовые к показу подписи
     (те же PRIORITY_DISPLAY/TONALITY_DISPLAY и lookup имён, что и
     src/bp4/pipeline.py::build_showcase_row), + updated_at = datetime.now(UTC)
     (не func.now() — та же ловушка, что и в остальной модели).
Так витрина остаётся консистентной для BI сразу, без ожидания следующего
прогона BP-4, а перезапуск BP-4 её не затрёт (categorized_at не старше
showcase_event.updated_at).
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.showcase import ShowcaseEventUpdate
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp4.constants import PRIORITY_DISPLAY, TONALITY_DISPLAY
from src.bp4.models import ShowcaseEvent


class ShowcaseCRUD:
    """Репозиторий ShowcaseEvent: чтение витрины + write-through правка."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, showcase_id: int) -> ShowcaseEvent | None:
        return await self.session.get(ShowcaseEvent, showcase_id)

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> Sequence[ShowcaseEvent]:
        stmt = (
            select(ShowcaseEvent)
            .order_by(ShowcaseEvent.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(
        self, showcase_id: int, data: ShowcaseEventUpdate
    ) -> ShowcaseEvent | None:
        """Write-through: правит categorized_event, зеркалит в showcase_event.

        exclude_unset=True — трогаем только переданные в PATCH поля, не
        затираем остальную разметку значениями по умолчанию схемы.
        """
        showcase = await self.get(showcase_id)
        if showcase is None:
            return None

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return showcase

        categorized = await self.session.get(
            CategorizedEvent, showcase.categorized_event_id
        )
        for field, value in changes.items():
            setattr(categorized, field, value)

        if 'priority' in changes:
            showcase.priority = PRIORITY_DISPLAY[categorized.priority]
        if 'tonality' in changes:
            showcase.tonality = TONALITY_DISPLAY[categorized.tonality]
        if 'category_id' in changes:
            category = await self.session.get(Category, categorized.category_id)
            showcase.category = category.name
        if 'action' in changes:
            showcase.action = categorized.action
        if 'deadline' in changes:
            showcase.deadline = categorized.deadline
        if 'department_id' in changes:
            department = (
                await self.session.get(Department, categorized.department_id)
                if categorized.department_id is not None
                else None
            )
            showcase.department = department.name if department else None
        if 'comment' in changes:
            showcase.comment = categorized.comment

        showcase.updated_at = datetime.now(UTC)
        await self.session.flush()
        return showcase
