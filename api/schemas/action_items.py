"""Pydantic-схемы плана действий BP-6 (`action_item`) для API.

ActionItemUpdate — один эндпоинт на обе роли (viewer/analyst/admin), не
два разных PATCH: сервис (api/service/action_items.py) сам обрубает
непозволенные для viewer поля перед вызовом CRUD, схема здесь не
разграничивает права — это забота бизнес-логики, не валидации.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator

from api.validators.showcase import require_at_least_one_field
from core.enums import ActionStatus


class ActionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    showcase_event_id: int
    task: str
    department_id: int
    assigned_user_id: int | None
    deadline: date | None
    expected_result: str | None
    status: ActionStatus
    created_at: datetime
    updated_at: datetime


class ActionItemCreate(BaseModel):
    """Тело POST /action-items — только analyst/admin (EditorDep)."""

    showcase_event_id: int
    task: str
    department_id: int
    assigned_user_id: int | None = None
    deadline: date | None = None
    expected_result: str | None = None


class ActionItemUpdate(BaseModel):
    """Тело PATCH /action-items/{id} — partial update, общее на все роли.

    viewer реально может провести только `status`/`expected_result` —
    остальные поля сервис молча отбрасывает для этой роли (см.
    ActionItemService.update_item), а не схема: тут одна схема на два
    уровня доступа, а не 422 на «чужое» поле.
    """

    task: str | None = None
    department_id: int | None = None
    assigned_user_id: int | None = None
    deadline: date | None = None
    expected_result: str | None = None
    status: ActionStatus | None = None

    _require_one_field = model_validator(mode='after')(
        require_at_least_one_field
    )
