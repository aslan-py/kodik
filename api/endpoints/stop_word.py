"""Справочник stop_word (BP-2): generic CRUD, см. api/endpoints/reference.py.

UniqueConstraint(phrase, type) — конфликт на составной паре ловится тем же
generic-обработчиком IntegrityError в ReferenceService (409).
"""

from api.endpoints.reference import build_reference_router
from api.schemas.stop_word import StopWordCreate, StopWordRead, StopWordUpdate
from src.bp2.models import StopWord

router = build_reference_router(
    StopWord,
    read_schema=StopWordRead,
    create_schema=StopWordCreate,
    update_schema=StopWordUpdate,
    search_field='phrase',
    not_found_message='Стоп-слово не найдено',
    tag='Стоп-слова',
)
