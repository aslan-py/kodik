"""Pydantic-схемы справочника stop_word (BP-2) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict

from core.enums import StopType


class StopWordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phrase: str
    type: StopType
    note: str | None
    is_active: bool


class StopWordCreate(BaseModel):
    phrase: str
    type: StopType
    note: str | None = None


class StopWordUpdate(BaseModel):
    phrase: str | None = None
    type: StopType | None = None
    note: str | None = None
    is_active: bool | None = None
