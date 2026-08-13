"""Pydantic-схема alert (BP-5) — только чтение (неизменяемый журнал)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from core.enums import AlertStatus, DeliveryMode, PriorityLevel


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    showcase_event_id: int
    event_type_id: int | None
    priority: PriorityLevel
    user_id: int
    channel_id: int
    mode: DeliveryMode
    status: AlertStatus
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None
