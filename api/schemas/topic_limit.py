"""Pydantic-схемы справочника topic_limit (BP-2) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict

from core.enums import LimitScope, LimitWindow


class TopicLimitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: LimitScope
    max_count: int
    window: LimitWindow
    note: str | None
    is_active: bool


class TopicLimitCreate(BaseModel):
    scope: LimitScope
    max_count: int
    window: LimitWindow = LimitWindow.week
    note: str | None = None


class TopicLimitUpdate(BaseModel):
    scope: LimitScope | None = None
    max_count: int | None = None
    window: LimitWindow | None = None
    note: str | None = None
