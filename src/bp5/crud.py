"""Слой доступа к данным BP-5: отбор событий, справочники, запись alert.

Методы (по потоку конвейера):
    select_pending_events   → события витрины под проверку детектором
    load_event_types        → активные типы + ключевые слова (для detect)
    load_routing_rules      → активные правила, двумя группами: по (тип,
                                приоритет) и по одному приоритету
                                (`RoutingRuleGroups`)
    load_channels             → справочник channel_id -> name (доставка)
    load_users                → справочник user_id -> User (контакты)
    insert_alerts            → запись пачки alert (ON CONFLICT DO NOTHING),
                                возвращает РЕАЛЬНО вставленные строки
    mark_alert_result         → точечно queued -> sent/failed после отправки
    mark_checked              → проставить alerted_at (событие проверено)

Сессия — в self.session (через __init__), методы её не принимают. Транзакцией
(commit/rollback) управляет вызывающий код — здесь только запросы.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import RowMapping, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import AlertStatus, PriorityLevel
from src.bp4.models import ShowcaseEvent
from src.bp5.models import Alert, Channel, EventType, RoutingRule, User


@dataclass
class RoutingRuleGroups:
    """Активные правила маршрутизации, сгруппированные для детектора.

    Два независимых словаря — правило с указанным типом события ищется
    только в `by_type`, правило без типа (срабатывает на любой тип нужного
    приоритета) — только в `by_priority`. Раздельные ключи вместо одного
    прохода с `event_type_id IS NULL OR event_type_id = ...` — тот же выбор,
    что и раньше: справочники грузятся один раз на прогон, без запроса на
    каждое событие (см. openspec/changes/add-priority-only-routing/design.md,
    Decisions).
    """

    by_type: dict[tuple[int, PriorityLevel], list[RoutingRule]] = field(
        default_factory=dict
    )
    by_priority: dict[PriorityLevel, list[RoutingRule]] = field(
        default_factory=dict
    )


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

    async def load_routing_rules(self) -> RoutingRuleGroups:
        """Активные правила, сгруппированные для детектора — см.
        `RoutingRuleGroups`. Правило с `event_type_id` попадает в `by_type`
        по ключу (тип, приоритет); правило без типа — в `by_priority` по
        ключу приоритет. Один запрос на весь прогон, без обращения к БД
        на каждое событие.
        """
        result = await self.session.execute(
            select(RoutingRule).where(RoutingRule.is_active)
        )
        groups = RoutingRuleGroups()
        for rule in result.scalars():
            if rule.event_type_id is not None:
                groups.by_type.setdefault(
                    (rule.event_type_id, rule.priority), []
                ).append(rule)
            else:
                groups.by_priority.setdefault(rule.priority, []).append(rule)
        return groups

    async def load_channels(self) -> dict[int, str]:
        """Справочник channel_id -> name. Нет relationship к Channel в
        RoutingRule/Alert (проект хранит только FK int), поэтому имя канала
        для решения «слать ли по email прямо сейчас» берётся отдельным
        плоским запросом, как и load_event_types/load_routing_rules.
        """
        result = await self.session.execute(select(Channel.id, Channel.name))
        return dict(result.all())

    async def load_users(self) -> dict[int, User]:
        """Справочник user_id -> User. Полный объект, не только email:
        telegram_id нужен для доставки в telegram, full_name — для текста
        письма."""
        result = await self.session.execute(select(User))
        return {u.id: u for u in result.scalars()}

    # ========================================================================
    #  Запись результата
    # ========================================================================

    async def insert_alerts(self, rows: Sequence[dict]) -> Sequence[RowMapping]:
        """Записать пачку alert. ON CONFLICT DO NOTHING — идемпотентность.

        UNIQUE(showcase_event_id, channel_id, user_id) гасит повтор: если
        событие уже проверялось и alert для этой пары (канал, получатель)
        есть, повторная проверка (например, из-за косметической
        переразметки) не продублирует отправку. commit — на вызывающем.

        Возвращает РЕАЛЬНО вставленные строки (RETURNING) — строки,
        попавшие в конфликт, Postgres в RETURNING не включает. По этому
        набору вызывающий код (sync_alerts) решает, для чего в этом
        прогоне действительно нужно попытаться отправить письмо/сообщение.
        """
        if not rows:
            return []
        stmt = pg_insert(Alert).values(list(rows))
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['showcase_event_id', 'channel_id', 'user_id']
        ).returning(
            Alert.id,
            Alert.showcase_event_id,
            Alert.channel_id,
            Alert.user_id,
            Alert.mode,
        )
        result = await self.session.execute(stmt)
        return result.mappings().all()

    async def mark_alert_result(
        self,
        alert_id: int,
        status: AlertStatus,
        sent_at: datetime | None,
        error_message: str | None,
    ) -> None:
        """Точечно обновить исход попытки доставки: queued -> sent/failed.

        Alert не имеет updated_at/onupdate (в отличие от showcase_event),
        так что self-reference трюк из mark_checked здесь не нужен.
        """
        await self.session.execute(
            Alert.__table__.update()
            .where(Alert.id == alert_id)
            .values(status=status, sent_at=sent_at, error_message=error_message)
        )

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
