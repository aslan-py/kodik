"""Pydantic-схемы справочника region (BP-2) для generic-CRUD API.

Region без ActiveMixin (статический справочник городов — is_active/soft-
delete не нужны, см. api/endpoints/region.py::soft_delete=False).
"""

from pydantic import BaseModel, ConfigDict


class RegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name_display: str
    name_aliases: list[str] | None
    macro_region: str | None
    latitude: float | None
    longitude: float | None


class RegionCreate(BaseModel):
    name_display: str
    name_aliases: list[str] | None = None
    macro_region: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class RegionUpdate(BaseModel):
    name_display: str | None = None
    name_aliases: list[str] | None = None
    macro_region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
