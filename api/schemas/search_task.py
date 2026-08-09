"""Pydantic-схемы search_task (BP-1, матрица задач сбора) для API."""

from pydantic import BaseModel, ConfigDict


class SearchTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    competitor_id: int
    source_id: int
    trigger_id: int | None
    is_active: bool


class SearchTaskCreate(BaseModel):
    competitor_id: int
    source_id: int
    trigger_id: int | None = None


class SearchTaskUpdate(BaseModel):
    competitor_id: int | None = None
    source_id: int | None = None
    trigger_id: int | None = None
