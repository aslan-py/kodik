"""Pydantic-схема raw_item (BP-1) — только чтение."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from core.enums import RawItemStatus


class RawItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    search_task_id: int
    status: RawItemStatus
    content_hash: str | None
    raw_data: dict | None
    html_file_path: str | None
    source_request_url: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
