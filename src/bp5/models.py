"""Модели BP-5 (детектор значимых событий + алертинг + маршрутизация).

Справочники:
- EventType: типы значимых событий + слова-маркеры для детекции
- Channel: каналы доставки (telegram, email, dashboard)
- User: конкретные получатели алертов (email, telegram)
- RoutingRule: матрица маршрутизации (тип + приоритет → получатель + канал
  + режим)

Журнал:
- Alert: что/кому/куда отправлено. История + защита от повторной отправки
  через UNIQUE(showcase_event_id, channel_id, user_id).

Адресат — конкретный User, а не Department. Список получателей курируется
вручную и может не совпадать со штатом отдела («сегодня трое, завтра один»),
поэтому Department не годится источником рассылки — он не говорит, КОМУ
конкретно слать. Отдел при этом не теряется: он виден через
User.department_id, просто не хранится отдельным полем в RoutingRule/Alert
(тот же принцип, что и у priority/mode — снимок факта, а не ссылка, которая
может разъехаться).

priority_level переиспользуется из BP-3 (enum общий для разметки и правил).
delivery_mode и alert_status — локальные enum'ы BP-5.

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActiveMixin, Base, Mixin, StrippedString
from core.enums import (
    AlertStatus,
    DeliveryMode,
    PriorityLevel,
    UserRole,
    alert_status,
    delivery_mode,
    priority_level,
    user_role,
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
        StrippedString(256),
        unique=True,
        comment=(
            'Название типа: судебный/надзорный риск, выигранный тендер, '
            'активный наём, расширение, M&A, закрытие объекта'
        ),
    )
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        comment=(
            'Слова-маркеры: [«прокуратура», «суд», «иск», «нарушения»]. '
            'По ним детектор матчит title события (вхождение подстроки)'
        ),
    )

    __table_args__ = (
        Index(
            'ix_event_type_keywords',
            'keywords',
            postgresql_using='gin',
        ),
        CheckConstraint(
            'name = btrim(name)', name='ck_event_type_name_trimmed'
        ),
    )


class Channel(Base, Mixin, ActiveMixin):
    """Справочник каналов доставки."""

    name: Mapped[str] = mapped_column(
        StrippedString(64),
        unique=True,
        comment='Канал доставки: telegram, email, dashboard',
    )

    __table_args__ = (
        CheckConstraint('name = btrim(name)', name='ck_channel_name_trimmed'),
    )


class User(Base, Mixin, ActiveMixin):
    """Получатели алертов — конкретные люди, не отделы.

    Также пользователь API: логинится по email+паролю (`password_hash`),
    доступ определяется `role` (ось прав, НЕ путать с department_id — тот
    просто «в каком отделе числится», справочно).

    department_id — справочно (в каком отделе числится), НЕ источник для
    рассылки: список получателей курируется вручную в routing_rule и может
    не совпадать со штатом отдела. is_active — уволен/в отпуске, гасим
    флагом, не удаляем (иначе потеряется история alert через FK RESTRICT).

    telegram_id нужен для алертов, но неизвестен на момент self-service
    регистрации по email — поэтому nullable: пользователь может залогиниться
    и работать в системе, но не получать telegram-алерты, пока сам не
    привяжет telegram_id.
    """

    full_name: Mapped[str | None] = mapped_column(
        StrippedString(256),
        comment='ФИО — для читаемости в админке, не критично',
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey('department.id', ondelete='RESTRICT'),
        comment='В каком отделе числится (справочно, не для маршрутизации)',
    )
    email: Mapped[str] = mapped_column(
        StrippedString(256),
        unique=True,
        comment='Адрес для канала email, он же логин API',
    )
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger,
        unique=True,
        comment=(
            'Числовой chat_id для канала telegram (sendMessage требует '
            'id, не @username). NULL, пока пользователь не привязал telegram'
        ),
    )
    password_hash: Mapped[str] = mapped_column(
        StrippedString(256),
        comment='bcrypt-хэш пароля для логина в API',
    )
    role: Mapped[UserRole] = mapped_column(
        user_role,
        default=UserRole.pending,
        server_default=text("'pending'"),
        comment=(
            'Уровень доступа к API (не отдел): pending/viewer/analyst/admin'
        ),
    )

    __table_args__ = (
        CheckConstraint(
            'full_name = btrim(full_name)', name='ck_user_full_name_trimmed'
        ),
        CheckConstraint('email = btrim(email)', name='ck_user_email_trimmed'),
    )


class PasswordResetCode(Base, Mixin):
    """Код сброса пароля (6 цифр), отправляется на email пользователя.

    Эфемерные данные (не audit-история, как Alert) — поэтому
    ondelete='CASCADE': удаление вместе с пользователем ничего не теряет.
    Один активный код на пользователя: при новом запросе сброса старые
    неиспользованные коды этого user_id удаляются (api/crud/users.py).
    code_hash — bcrypt через тот же hash_password/verify_password, что и
    пароли (api/security.py), отдельный механизм хэширования не заводим.
    """

    user_id: Mapped[int] = mapped_column(
        ForeignKey('user.id', ondelete='CASCADE'),
        comment='Кому принадлежит код',
    )
    code_hash: Mapped[str] = mapped_column(
        StrippedString(256), comment='bcrypt-хэш 6-значного кода'
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment='Когда код перестаёт быть валиден'
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment='Когда код использован (успешно или исчерпаны попытки)',
    )
    attempts: Mapped[int] = mapped_column(
        default=0,
        server_default=text('0'),
        comment='Число неверных попыток ввода — защита от перебора',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Когда код сгенерирован',
    )


class RoutingRule(Base, Mixin, ActiveMixin):
    """Матрица маршрутизации: тип + приоритет → получатель + канал + режим.

    Аналитик заполняет заранее. Детектор находит event_type_id и priority
    события, читает подходящие строки правила: «если событие такого типа
    и такого приоритета — шли туда-то». Несколько получателей и/или каналов
    на пару (тип, приоритет) = несколько строк = несколько доставок; чтобы
    добавить или убрать адресата, просто добавляют/деактивируют строку —
    без правки кода.
    """

    event_type_id: Mapped[int] = mapped_column(
        ForeignKey('event_type.id', ondelete='RESTRICT'),
        comment='Для какого типа значимого события',
    )
    priority: Mapped[PriorityLevel] = mapped_column(
        priority_level,
        comment='Для какого приоритета срабатывает правило',
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey('user.id', ondelete='RESTRICT'),
        comment='Кому конкретно отправлять',
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
            'user_id',
            name='uq_routing_rule_type_priority_channel_user',
        ),
    )


# ============================================================================
#  Журнал BP-5 — алерты
# ============================================================================


class Alert(Base, Mixin):
    """Журнал алертинга BP-5: что/кому/куда отправлено.

    Одна строка = одна доставка одному получателю. priority, mode и user_id —
    СНИМОК факта на момент алерта (правило завтра поменяют, пользователь
    сменит отдел — а история остаётся). Порядок: пишем queued → отправляем →
    обновляем на sent/failed. UNIQUE(событие, канал, получатель) защищает
    от повторной отправки.
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey('user.id', ondelete='RESTRICT'),
        comment='Кому ушло',
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
            'user_id',
            name='uq_alert_event_channel_user',
        ),
    )
