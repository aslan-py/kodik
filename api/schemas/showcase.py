"""Pydantic-схемы витрины BP-4 для API.

ShowcaseEventUpdate — поля разметки, как их хранит categorized_event
(enum'ы priority/tonality, id категории/отдела), НЕ как их хранит витрина
(готовые строки-подписи). ShowcaseCRUD.update() сам переводит одно в другое.
Факты (title/media/region/...) сюда не входят — они не редактируются через
этот эндпоинт (см. FASTAPI_PLAN.md, п.3).
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from api.validators.showcase import require_at_least_one_field
from core.enums import PriorityLevel, TonalityLevel


class ShowcaseEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    categorized_event_id: int
    raw_item_id: int
    published_at: date | None
    title: str
    media: str | None
    region: str | None
    macro_region: str | None
    latitude: float | None
    longitude: float | None
    competitor: str | None
    source_url: str | None
    priority: str
    category: str
    tonality: str
    media_index: Decimal | None
    action: str | None
    deadline: date | None
    department: str | None
    comment: str | None
    updated_at: datetime
    alerted_at: datetime | None


class ShowcaseEventUpdate(BaseModel):
    """PATCH /showcase/{id} — только поля разметки, все опциональны."""

    priority: PriorityLevel | None = None
    category_id: int | None = None
    tonality: TonalityLevel | None = None
    action: str | None = None
    deadline: date | None = None
    department_id: int | None = None
    comment: str | None = None

    _require_one_field = model_validator(mode='after')(
        require_at_least_one_field
    )
