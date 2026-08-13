"""Единый endpoint вариантов фильтров витрины и плана действий."""

from fastapi import APIRouter

from api.dependencies import SessionDep, ViewerDep
from api.responses import ACTION_ITEM_LIST_RESPONSES
from api.schemas.filter_options import FilterOptionsRead
from api.service.filter_options import FilterOptionsService

router = APIRouter()


@router.get(
    '',
    response_model=FilterOptionsRead,
    responses=ACTION_ITEM_LIST_RESPONSES,
    summary='Варианты фильтров витрины и плана действий',
    description=(
        'Доступ: `viewer`, `analyst`, `admin` (не `pending`). '
        'ID-зависимые варианты возвращаются как `{value, label}`, '
        'сроки — в ISO-формате `YYYY-MM-DD`. Для `viewer` варианты '
        'плана действий ограничены задачами его отдела.'
    ),
)
async def get_filter_options(
    session: SessionDep, viewer: ViewerDep
) -> FilterOptionsRead:
    return await FilterOptionsService(session).get_options(viewer)
