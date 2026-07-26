"""Модели BP-5 (детектор значимых событий + алертинг + маршрутизация).

Справочники:
- EventType: типы значимых событий + слова-маркеры для детекции
- Channel: каналы доставки (telegram, email, dashboard)
- RoutingRule: матрица маршрутизации (тип + приоритет → отдел + канал + режим)

Журнал:
- Alert: что/кому/куда отправлено. История + защита от повторной отправки
  через UNIQUE(showcase_event_id, channel_id).

priority_level переиспользуется из BP-3 (enum общий для разметки и правил).
delivery_mode и alert_status — локальные enum'ы BP-5.

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActiveMixin, Base, Mixin
from core.enums import (
    AlertStatus,
    DeliveryMode,
    PriorityLevel,
    alert_status,
    delivery_mode,
    priority_level,
)

# ============================================================================
#  Справочники BP-5
# ============================================================================


class EventType(Base, Mixin, ActiveMixin):
    """Типы значимых событий + слова-маркеры для детекции.

    keywords — то, чем ЛОВИМ событие (ищем вхождения в title витрины);
    name — как тип НАЗЫВАЕТСЯ (для отчёта и поиска правила маршрутизации).
    """

    name: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        comment=(
            'Название типа: судебный/надзорный риск, выигранный тендер, '
            'активный наём, расширение, M&A, закрытие объекта'
        ),
    )
    keywords: Mapped[str] = mapped_column(
        Text,
        comment=(
            'Слова-маркеры через запятую: «прокуратура, суд, иск, нарушения». '
            'По ним детектор матчит title события'
        ),
    )


class Channel(Base, Mixin, ActiveMixin):
    """Справочник каналов доставки."""

    name: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        comment='Канал доставки: telegram, email, dashboard',
    )


class RoutingRule(Base, Mixin, ActiveMixin):
    """Матрица маршрутизации: тип + приоритет → отдел + канал + режим.

    Аналитик заполняет заранее. Детектор находит event_type_id и priority
    события, читает подходящие строки правила: «если событие такого типа
    и такого приоритета — шли туда-то». Несколько каналов на пару
    (тип, приоритет) = несколько строк = несколько доставок.
    """

    event_type_id: Mapped[int] = mapped_column(
        ForeignKey('event_type.id', ondelete='RESTRICT'),
        comment='Для какого типа значимого события',
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        priority_level,
        comment='Для какого приоритета срабатывает правило',
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey('department.id', ondelete='RESTRICT'),
        comment='На какой отдел маршрутизируем',
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey('channel.id', ondelete='RESTRICT'),
        comment='В какой канал доставляем',
    )
    mode: Mapped[DeliveryMode] = mapped_column(
        delivery_mode,
        comment='instant (П1) | digest (П2)',
    )

    __table_args__ = (
        UniqueConstraint(
            'event_type_id',
            'priority',
            'channel_id',
            name='uq_routing_rule_type_priority_channel',
        ),
    )


# ============================================================================
#  Журнал BP-5 — алерты
# ============================================================================


class Alert(Base, Mixin):
    """Журнал алертинга BP-5: что/кому/куда отправлено.

    Одна строка = одна доставка. priority и mode — СНИМОК факта на момент
    алерта (правило завтра поменяют, а история остаётся). Порядок: пишем
    queued → отправляем → обновляем на sent/failed. UNIQUE(событие, канал)
    защищает от повторной отправки.
    """

    showcase_event_id: Mapped[int] = mapped_column(
        ForeignKey('showcase_event.id', ondelete='RESTRICT'),
        comment='По какому событию витрины сработал алерт',
    )
    event_type_id: Mapped[int] = mapped_column(
        ForeignKey('event_type.id', ondelete='RESTRICT'),
        comment='Какой тип значимого события распознан',
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        priority_level,
        comment='Приоритет события на момент алерта (снимок)',
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey('department.id', ondelete='RESTRICT'),
        comment='Кому ушло (отдел)',
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey('channel.id', ondelete='RESTRICT'),
        comment='Каким каналом',
    )
    mode: Mapped[DeliveryMode] = mapped_column(
        delivery_mode,
        comment=(
            'Снимок режима из правила: instant | digest. '
            'По нему джоба-сводка находит свои алерты'
        ),
    )
    status: Mapped[AlertStatus] = mapped_column(
        alert_status,
        default=AlertStatus.queued,
        server_default=text("'queued'"),
        comment='queued → sent / failed',
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        comment='Текст ошибки при status=failed',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Когда завели алерт',
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment='Когда фактически доставлено',
    )

    __table_args__ = (
        UniqueConstraint(
            'showcase_event_id',
            'channel_id',
            name='uq_alert_event_channel',
        ),
    )
