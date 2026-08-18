"""Pydantic-схемы справочника trigger (BP-1) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict


class TriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword: str
    is_active: bool


class TriggerCreate(BaseModel):
    keyword: str


class TriggerUpdate(BaseModel):
    keyword: str | None = None
    is_active: bool | None = None
