"""Pydantic-схема source_candidate (BP-7) — только чтение.

Заполняет агент расширения источников (следующая итерация) и переносит
SourceCandidatePromoter (src/bp7/pipeline.py) — здесь только просмотр
очереди, без CRUD: правка/удаление кандидатов через API не предусмотрены.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from core.enums import SourceCandidateStatus


class SourceCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    competitor_id: int | None
    url: str | None
    score: Decimal | None
    status: SourceCandidateStatus
    is_active: bool
    created_at: datetime
