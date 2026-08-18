"""alert (BP-5): только просмотр. GET '' (фильтры), GET '/{id}'.

Неизменяемый журнал доставки (пишет src/bp5/pipeline.py::sync_alerts) —
правка status/error_message задним числом испортила бы историю. Доступ —
только analyst/admin.
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from api.dependencies import SessionDep, require_role
from api.responses import REFERENCE_DETAIL_RESPONSES, REFERENCE_LIST_RESPONSES
from api.schemas.alert import AlertRead
from api.service.pipeline_view import AlertService
from core.enums import AlertStatus, DeliveryMode, PriorityLevel, UserRole

router = APIRouter()
_editor_only = [Depends(require_role(UserRole.analyst, UserRole.admin))]


@router.get(
    '',
    response_model=list[AlertRead],
    responses=REFERENCE_LIST_RESPONSES,
    dependencies=_editor_only,
    summary='Список отправленных уведомлений (alert)',
    description=(
        'Доступ: только `analyst` и `admin`. Фильтры: `status`, '
        '`channel_id`, `user_id`, `priority`, `mode` — точное совпадение; '
        '`created_from/to`, `sent_from/to` — диапазон дат.'
    ),
)
async def list_alerts(
    session: SessionDep,
    status: AlertStatus | None = None,
    channel_id: int | None = None,
    user_id: int | None = None,
    priority: PriorityLevel | None = None,
    mode: DeliveryMode | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sent_from: datetime | None = None,
    sent_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AlertRead]:
    items = await AlertService(session).list_items(
        status=status,
        channel_id=channel_id,
        user_id=user_id,
        priority=priority,
        mode=mode,
        created_from=created_from,
        created_to=created_to,
        sent_from=sent_from,
        sent_to=sent_to,
        limit=limit,
        offset=offset,
    )
    return [AlertRead.model_validate(i) for i in items]


@router.get(
    '/{item_id}',
    response_model=AlertRead,
    responses=REFERENCE_DETAIL_RESPONSES,
    dependencies=_editor_only,
    summary='alert по id',
    description='Доступ: только `analyst` и `admin`.',
)
async def read_alert(item_id: int, session: SessionDep) -> AlertRead:
    item = await AlertService(session).get_item(item_id)
    return AlertRead.model_validate(item)
