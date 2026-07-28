"""Слой доступа к данным BP-5: отбор событий, справочники, запись alert.

Методы (по потоку конвейера):
    select_pending_events   → события витрины под проверку детектором
    load_event_types        → активные типы + ключевые слова (для detect)
    load_routing_rules      → активные правила по (тип, приоритет)
    insert_alerts            → запись пачки alert (ON CONFLICT DO NOTHING)
    mark_checked              → проставить alerted_at (событие проверено)

Сессия — в self.session (через __init__), методы её не принимают. Транзакцией
(commit/rollback) управляет вызывающий код — здесь только запросы.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import PriorityLevel
from src.bp4.models import ShowcaseEvent
from src.bp5.models import Alert, EventType, RoutingRule


class Bp5Crud:
    """Репозиторий BP-5: отбор витрины, справочники детектора, журнал alert."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    #  Отбор входных событий
    # ========================================================================

    async def select_pending_events(self) -> Sequence[ShowcaseEvent]:
        """События витрины, которым нужна проверка детектором.

        Два случая: alerted_at ещё не проставлен (новое событие) ИЛИ
        updated_at > alerted_at (BP-4 переписал строку после переразметки —
        проверяем заново). НЕ по журналу alert: там легитимны события
        с нулём строк (проверили — не значимо), и по нему нельзя отличить
        «ещё не проверено» от «проверено, но не сработало».
        """
        stmt = select(ShowcaseEvent).where(
            or_(
                ShowcaseEvent.alerted_at.is_(None),
                ShowcaseEvent.updated_at > ShowcaseEvent.alerted_at,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    # ========================================================================
    #  Справочники детектора
    # ========================================================================

    async def load_event_types(self) -> Sequence[EventType]:
        """Активные типы событий (name + keywords) — для сверки с title."""
        result = await self.session.execute(
            select(EventType).where(EventType.is_active)
        )
        return result.scalars().all()

    async def load_routing_rules(
        self,
    ) -> dict[tuple[int, PriorityLevel], list[RoutingRule]]:
        """Активные правила, сгруппированные по (event_type_id, priority).

        Такая группировка — прямое попадание в то, как их использует
        детектор: нашёл тип и приоритет события → взял готовый список
        правил без отдельного запроса на каждое событие.
        """
        result = await self.session.execute(
            select(RoutingRule).where(RoutingRule.is_active)
        )
        grouped: dict[tuple[int, PriorityLevel], list[RoutingRule]] = {}
        for rule in result.scalars():
            grouped.setdefault((rule.event_type_id, rule.priority), []).append(
                rule
            )
        return grouped

    # ========================================================================
    #  Запись результата
    # ========================================================================

    async def insert_alerts(self, rows: Sequence[dict]) -> int:
        """Записать пачку alert. ON CONFLICT DO NOTHING — идемпотентность.

        UNIQUE(showcase_event_id, channel_id, user_id) гасит повтор: если
        событие уже проверялось и alert для этой пары (канал, получатель)
        есть, повторная проверка (например, из-за косметической
        переразметки) не продублирует отправку. commit — на вызывающем.
        """
        if not rows:
            return 0
        stmt = pg_insert(Alert).values(list(rows))
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['showcase_event_id', 'channel_id', 'user_id']
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def mark_checked(
        self, event_ids: Sequence[int], checked_at: datetime
    ) -> None:
        """Проставить alerted_at пачке событий — независимо от результата.

        checked_at приходит снаружи (один снимок времени на весь прогон),
        а не берётся здесь через now(): единообразие со временем, которым
        помечены сами вставленные alert-строки того же прогона.

        updated_at ЯВНО перезаписываем его же текущим значением
        (self-reference на уровне SQL). Без этого bulk UPDATE запустил бы
        column-level onupdate этого поля (он срабатывает на ЛЮБОМ UPDATE
        через SQLAlchemy, не только на точечной ORM-правке — см. заметку
        в categorized_at, src/bp3/models.py), и updated_at сдвинулся бы
        почти в ту же секунду, что alerted_at. При микросекундной разнице
        условие «updated_at > alerted_at» могло бы стать истинным, и
        событие вернулось бы в отбор снова.
        """
        if not event_ids:
            return
        await self.session.execute(
            ShowcaseEvent.__table__.update()
            .where(ShowcaseEvent.id.in_(event_ids))
            .values(
                alerted_at=checked_at,
                updated_at=ShowcaseEvent.updated_at,
            )
        )
