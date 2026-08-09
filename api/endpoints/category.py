"""Справочник category (BP-3): generic CRUD, см. api/endpoints/reference.py."""

from api.endpoints.reference import build_reference_router
from api.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from src.bp3.models import Category

router = build_reference_router(
    Category,
    read_schema=CategoryRead,
    create_schema=CategoryCreate,
    update_schema=CategoryUpdate,
    search_field='name',
    not_found_message='Категория не найдена',
    tag='Категория',
)
