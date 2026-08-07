"""Pydantic-схема categorized_event (BP-3) — только чтение.

Правка разметки — через существующий `PATCH /showcase/{id}`
(api/endpoints/showcase.py), не здесь: отдельный прямой PATCH сломал бы
зеркалирование в showcase_event (см. api/FASTAPI_PLAN.md, раздел 3).
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from core.enums import PriorityLevel, TonalityLevel


class CategorizedEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    normalized_item_id: int
    priority: PriorityLevel
    category_id: int
    tonality: TonalityLevel
    media_index: Decimal | None
    action: str | None
    task: list[str] | None
    deadline: date | None
    department_id: int | None
    comment: str | None
    expected_result: str | None
    llm_model: str | None
    prompt_version: str | None
    categorized_at: datetime
