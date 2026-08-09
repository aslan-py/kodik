"""Справочник routing_rule (BP-5): generic CRUD, см. api/endpoints/reference.py.

Нет строкового поля под поиск (4 FK + 2 enum) — search_field=None.
UniqueConstraint(event_type_id, priority, channel_id, user_id) и битые FK
(event_type_id/user_id/channel_id) ловятся generic-обработчиком в
ReferenceService (409/404 соответственно).
"""

from api.endpoints.reference import build_reference_router
from api.schemas.routing_rule import (
    RoutingRuleCreate,
    RoutingRuleRead,
    RoutingRuleUpdate,
)
from src.bp5.models import RoutingRule

router = build_reference_router(
    RoutingRule,
    read_schema=RoutingRuleRead,
    create_schema=RoutingRuleCreate,
    update_schema=RoutingRuleUpdate,
    search_field=None,
    not_found_message='Правило маршрутизации не найдено',
    tag='Правила маршрутизации',
)
