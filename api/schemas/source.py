"""Pydantic-схемы справочника source (BP-1) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


class SourceCreate(BaseModel):
    name: str


class SourceUpdate(BaseModel):
    name: str | None = None
