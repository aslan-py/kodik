"""Pydantic-схемы справочника routing_rule (BP-5) для generic-CRUD API."""

from pydantic import BaseModel, ConfigDict

from core.enums import DeliveryMode, PriorityLevel


class RoutingRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type_id: int | None
    priority: PriorityLevel
    user_id: int
    channel_id: int
    mode: DeliveryMode
    is_active: bool


class RoutingRuleCreate(BaseModel):
    # Пусто — правило по приоритету: срабатывает на любой тип события
    # этого приоритета, без проверки заголовка.
    event_type_id: int | None = None
    priority: PriorityLevel
    user_id: int
    channel_id: int
    mode: DeliveryMode


class RoutingRuleUpdate(BaseModel):
    # PATCH — partial update (api/endpoints/reference.py: exclude_unset=True):
    # поле отсутствует в запросе -> не меняется; передано явным null ->
    # тип очищается (правило становится правилом по приоритету).
    event_type_id: int | None = None
    priority: PriorityLevel | None = None
    user_id: int | None = None
    channel_id: int | None = None
    mode: DeliveryMode | None = None
    is_active: bool | None = None
