"""Справочник region (BP-2): generic CRUD, см. api/endpoints/reference.py.

soft_delete=False — Region без ActiveMixin (статический справочник городов,
"выключать" нечего) — нет DELETE, is_active не участвует в фильтре.
"""

from api.endpoints.reference import build_reference_router
from api.schemas.region import RegionCreate, RegionRead, RegionUpdate
from src.bp2.models import Region

router = build_reference_router(
    Region,
    read_schema=RegionRead,
    create_schema=RegionCreate,
    update_schema=RegionUpdate,
    search_field='name_display',
    not_found_message='Регион не найден',
    tag='Регион',
    soft_delete=False,
)
