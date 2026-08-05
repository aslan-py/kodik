"""Pydantic-схемы справочника event_type (BP-5) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict


class EventTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    keywords: list[str]
    is_active: bool


class EventTypeCreate(BaseModel):
    name: str
    keywords: list[str]


class EventTypeUpdate(BaseModel):
    name: str | None = None
    keywords: list[str] | None = None
