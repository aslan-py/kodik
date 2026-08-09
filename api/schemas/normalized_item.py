"""Pydantic-схема normalized_item (BP-2) — только чтение."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from core.enums import NormStatus, RejectReason


class NormalizedItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_item_id: int
    competitor_id: int | None
    region_id: int | None
    source_id: int | None
    published_at: date | None
    title: str
    media_name: str | None
    media_domain: str | None
    url: str | None
    text: str | None
    extra: dict | None
    dedup_key: str
    status: NormStatus
    reject_reason: RejectReason | None
    created_at: datetime
