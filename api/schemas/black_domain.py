"""Pydantic-схемы справочника black_domain (BP-2) для generic-CRUD API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BlackDomainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    reason: str | None
    created_at: datetime
    is_active: bool


class BlackDomainCreate(BaseModel):
    domain: str
    reason: str | None = None


class BlackDomainUpdate(BaseModel):
    domain: str | None = None
    reason: str | None = None
    is_active: bool | None = None
