"""Pydantic-схемы справочника channel (BP-5) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict


class ChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool


class ChannelCreate(BaseModel):
    name: str


class ChannelUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
