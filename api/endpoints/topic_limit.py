"""Справочник topic_limit (BP-2): generic CRUD, см. api/endpoints/reference.py.

Нет строкового поля под поиск (scope/window — enum, не текст для ilike) —
search_field=None, только фильтр is_active + пагинация.
"""

from api.endpoints.reference import build_reference_router
from api.schemas.topic_limit import (
    TopicLimitCreate,
    TopicLimitRead,
    TopicLimitUpdate,
)
from src.bp2.models import TopicLimit

router = build_reference_router(
    TopicLimit,
    read_schema=TopicLimitRead,
    create_schema=TopicLimitCreate,
    update_schema=TopicLimitUpdate,
    search_field=None,
    not_found_message='Лимит анти-шума не найден',
    tag='Лимиты анти-шума',
)
