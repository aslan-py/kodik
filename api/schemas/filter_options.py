"""Схемы вариантов фильтров для витрины и плана действий."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from core.enums import ActionStatus


class IdLabelOption(BaseModel):
    value: int
    label: str


class ShowcaseFilterOptions(BaseModel):
    category: list[str]
    region: list[str]
    priority: list[str]
    competitor: list[str]
    department: list[str]
    media: list[str]


class DeadlineRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: date | None = Field(default=None, alias='from')
    to: date | None = None


class ActionItemFilterOptions(BaseModel):
    status: list[ActionStatus]
    deadline: DeadlineRange
    priority: list[str]
    assigned_user_id: list[IdLabelOption]
    department_id: list[IdLabelOption]


class FilterOptionsRead(BaseModel):
    showcase: ShowcaseFilterOptions
    action_items: ActionItemFilterOptions
