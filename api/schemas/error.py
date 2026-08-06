"""Схема ошибки для документации Swagger.

Описывает РЕАЛЬНЫЙ формат ответа: хэндлеры ошибок не переопределялись,
FastAPI сам оборачивает `HTTPException(detail=...)` в `{"detail": "..."}` —
эта схема только даёт Swagger модель для `responses={...}` (см.
`api/responses.py`), поведение приложения не меняет.
"""

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    """`{"detail": "..."}` — стандартный формат HTTPException FastAPI."""

    detail: str

    model_config = ConfigDict(json_schema_extra={'description': ''})
