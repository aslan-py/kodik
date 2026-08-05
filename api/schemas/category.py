"""Pydantic-схемы справочника category (BP-3) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    note: str | None
    is_active: bool


class CategoryCreate(BaseModel):
    name: str
    note: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    note: str | None = None
