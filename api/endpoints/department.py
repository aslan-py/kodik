"""Справочник department (BP-3): generic CRUD, см. api/endpoints/reference.py.

public_read=True — GET-роуты без токена: department_id выбирается ДО
логина (POST /auth/register) и в профиле pending-пользователя
(PATCH /users/me) — фронту нужен способ получить список отделов до того,
как есть JWT. POST/PATCH/DELETE остаются только analyst/admin.
"""

from api.endpoints.reference import build_reference_router
from api.schemas.department import (
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
)
from src.bp3.models import Department

router = build_reference_router(
    Department,
    read_schema=DepartmentRead,
    create_schema=DepartmentCreate,
    update_schema=DepartmentUpdate,
    search_field='name',
    not_found_message='Отдел не найден',
    tag='Отдел',
    public_read=True,
)
