"""Справочник black_domain (BP-2): generic CRUD, см. api/endpoints/reference."""

from api.endpoints.reference import build_reference_router
from api.schemas.black_domain import (
    BlackDomainCreate,
    BlackDomainRead,
    BlackDomainUpdate,
)
from src.bp2.models import BlackDomain

router = build_reference_router(
    BlackDomain,
    read_schema=BlackDomainRead,
    create_schema=BlackDomainCreate,
    update_schema=BlackDomainUpdate,
    search_field='domain',
    not_found_message='Домен в чёрном списке не найден',
    tag='Чёрный список доменов',
)
