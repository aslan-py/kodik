"""Локальная изоляция BP-5 от заранее сохранённого состояния БД."""

import pytest
from sqlalchemy import or_, update

from src.bp4.models import ShowcaseEvent
from src.bp5.models import EventType, RoutingRule


@pytest.fixture(autouse=True)
async def isolate_bp5_baseline(session):
    """Скрывает старые входы детектора внутри откатываемой транзакции.

    Фикстура выполняется до fixture-данных конкретного теста. Поэтому новые
    event_type и routing_rule остаются активными, а старые pending-события не
    попадают в ``sync_alerts``. ``flush`` не фиксирует изменения: после теста
    общая fixture ``session`` возвращает исходное состояние рабочей БД.
    """
    await session.execute(
        update(EventType)
        .where(EventType.is_active.is_(True))
        .values(is_active=False)
    )
    await session.execute(
        update(RoutingRule)
        .where(RoutingRule.is_active.is_(True))
        .values(is_active=False)
    )
    await session.execute(
        update(ShowcaseEvent)
        .where(
            or_(
                ShowcaseEvent.alerted_at.is_(None),
                ShowcaseEvent.updated_at > ShowcaseEvent.alerted_at,
            )
        )
        .values(alerted_at=ShowcaseEvent.updated_at)
    )
    await session.flush()
