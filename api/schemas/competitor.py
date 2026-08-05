"""Pydantic-схемы справочника competitor (BP-1) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict


class CompetitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    inn: str | None
    is_active: bool


class CompetitorCreate(BaseModel):
    name: str
    inn: str | None = None


class CompetitorUpdate(BaseModel):
    name: str | None = None
    inn: str | None = None
