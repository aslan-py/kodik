"""Справочник trigger (BP-1): generic CRUD, см. api/endpoints/reference.py."""

from api.endpoints.reference import build_reference_router
from api.schemas.trigger import TriggerCreate, TriggerRead, TriggerUpdate
from src.bp1.models import Trigger

router = build_reference_router(
    Trigger,
    read_schema=TriggerRead,
    create_schema=TriggerCreate,
    update_schema=TriggerUpdate,
    search_field='keyword',
    not_found_message='Триггер не найден',
    tag='Триггер',
)
