"""Pydantic-схемы справочника department (BP-3) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    note: str | None
    is_active: bool


class DepartmentCreate(BaseModel):
    name: str
    note: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = None
    note: str | None = None
