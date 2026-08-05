"""Справочник competitor (BP-1): generic CRUD, см. api/endpoints/reference."""

from api.endpoints.reference import build_reference_router
from api.schemas.competitor import (
    CompetitorCreate,
    CompetitorRead,
    CompetitorUpdate,
)
from src.bp1.models import Competitor

router = build_reference_router(
    Competitor,
    read_schema=CompetitorRead,
    create_schema=CompetitorCreate,
    update_schema=CompetitorUpdate,
    search_field='name',
    not_found_message='Конкурент не найден',
    tag='Конкурент',
)
