"""Справочник event_type (BP-5): generic CRUD, см. api/endpoints/reference."""

from api.endpoints.reference import build_reference_router
from api.schemas.event_type import (
    EventTypeCreate,
    EventTypeRead,
    EventTypeUpdate,
)
from src.bp5.models import EventType

router = build_reference_router(
    EventType,
    read_schema=EventTypeRead,
    create_schema=EventTypeCreate,
    update_schema=EventTypeUpdate,
    search_field='name',
    not_found_message='Тип события не найден',
    tag='Типы значимых событий',
)
