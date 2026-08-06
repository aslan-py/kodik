"""Справочник channel (BP-5): generic CRUD, см. api/endpoints/reference.py."""

from api.endpoints.reference import build_reference_router
from api.schemas.channel import ChannelCreate, ChannelRead, ChannelUpdate
from src.bp5.models import Channel

router = build_reference_router(
    Channel,
    read_schema=ChannelRead,
    create_schema=ChannelCreate,
    update_schema=ChannelUpdate,
    search_field='name',
    not_found_message='Канал доставки не найден',
    tag='Каналы доставки',
)
