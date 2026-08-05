"""Справочник source (BP-1): generic CRUD, см. api/endpoints/reference.py."""

from api.endpoints.reference import build_reference_router
from api.schemas.source import SourceCreate, SourceRead, SourceUpdate
from src.bp1.models import Source

router = build_reference_router(
    Source,
    read_schema=SourceRead,
    create_schema=SourceCreate,
    update_schema=SourceUpdate,
    search_field='name',
    not_found_message='Источник не найден',
    tag='Источник',
)
