"""Единый модуль enum'ов проекта.

Держим здесь ВСЕ перечисления пайплайна (BP-1…BP-7), а не в моделях:
часть из них делит несколько таблиц (priority_level — BP-3 и BP-5;
delivery_mode — routing_rule и alert), и разбрасывать их по моделям неудобно.

На каждый enum — две сущности:
- Python-класс `StrEnum` (значения, аннотации `Mapped[...]`, бизнес-логика);
- общий экземпляр SQLAlchemy `Enum` в snake_case (тип колонки).

Экземпляр типа ОДИН на enum и переиспользуется всеми колонками: так
PostgreSQL CREATE TYPE выполняется единожды (отдельные `Enum(...)` с одинаковым
`name` дали бы дубль DDL). Имя SA-инстанса = имя PG-типа, чтобы читалось
`mapped_column(priority_level)`.
"""

import enum

from sqlalchemy import Enum

# ============================================================================
#  BP-1 — сбор данных
# ============================================================================


class RawItemStatus(enum.StrEnum):
    """Статус снимка (выгрузки) в raw_item.

    new/changed = новая строка (история версий); error = сбой сбора.
    Если хэш совпал (ничего не изменилось) — новую строку НЕ создаём и статус
    НЕ трогаем, только обновляем updated_at у последней строки.
    """

    new = 'new'
    changed = 'changed'
    error = 'error'


# ============================================================================
#  BP-2 — нормализация и фильтрация
# ============================================================================


class StopType(enum.StrEnum):
    """Тип записи в таблице stop_word."""

    stop_word = 'stop_word'
    stop_topic = 'stop_topic'
    false_positive = 'false_positive'


class LimitScope(enum.StrEnum):
    """Разрез агрегации для антишум-лимита."""

    competitor = 'competitor'
    source = 'source'
    media = 'media'
    region = 'region'


class LimitWindow(enum.StrEnum):
    """Временное окно для антишум-лимита."""

    run = 'run'
    day = 'day'
    week = 'week'


class NormStatus(enum.StrEnum):
    """Статус нормализованного события."""

    ok = 'ok'
    rejected = 'rejected'


class RejectReason(enum.StrEnum):
    """Причина отсева нормализованного события."""

    black_domain = 'black_domain'
    stop_word = 'stop_word'
    stop_topic = 'stop_topic'
    false_positive = 'false_positive'
    noise_limit = 'noise_limit'
    parse_error = 'parse_error'


# ============================================================================
#  BP-3 — LLM-категоризация (priority/tonality делятся с BP-5)
# ============================================================================


class PriorityLevel(enum.StrEnum):
    """Приоритет события по четырёхуровневой шкале ТЗ.

    p1 — реагировать немедленно (срок 48ч);
    p2 — отслеживать (срок 1 неделя);
    p3 — к сведению (фоновая активность);
    p4 — игнорировать (шум, нерелевантный контент).
    """

    p1 = 'p1'
    p2 = 'p2'
    p3 = 'p3'
    p4 = 'p4'


class TonalityLevel(enum.StrEnum):
    """Тональность события."""

    positive = 'positive'
    neutral = 'neutral'
    negative = 'negative'
    alarming = 'alarming'
    irrelevant = 'irrelevant'


# ============================================================================
#  BP-5 — алертинг и маршрутизация
# ============================================================================


class DeliveryMode(enum.StrEnum):
    """Способ доставки алерта (не статус).

    instant — шлём сразу по событию (П1);
    digest — копим и отправляем пакетом по расписанию (П2).
    """

    instant = 'instant'
    digest = 'digest'


class AlertStatus(enum.StrEnum):
    """Статус доставки алерта."""

    queued = 'queued'
    sent = 'sent'
    failed = 'failed'


# ============================================================================
#  API — авторизация (роль ≠ отдел, роль — отдельная ось прав доступа)
# ============================================================================


class UserRole(enum.StrEnum):
    """Роль пользователя API — уровень доступа, не отдел (department_id).

    pending — только что зарегистрировался, доступа нет (кроме GET /users/me);
    viewer — читает витрину/свои задачи, править не может;
    analyst — правит витрину, подтверждает pending → viewer/analyst;
    admin — + управление пользователями/справочниками.
    """

    pending = 'pending'
    viewer = 'viewer'
    analyst = 'analyst'
    admin = 'admin'


# ============================================================================
#  BP-6 — план действий
# ============================================================================


class ActionStatus(enum.StrEnum):
    """Статус задачи из плана действий."""

    open = 'open'
    in_progress = 'in_progress'
    done = 'done'


# ============================================================================
#  BP-7 — расширение источников
# ============================================================================


class SourceCandidateStatus(enum.StrEnum):
    """Статус кандидата в источники: обработан ли переносом в source.

    new — ещё не проверялся переносом (или проверялся, но score/threshold
    не прошёл); promoted — перенесён в source. Двух значений достаточно:
    отбор кандидатов на перенос идёт напрямую по индексу на status, без
    JOIN/NOT EXISTS с source на каждый прогон (см. src/bp7/pipeline.py).
    """

    new = 'new'
    promoted = 'promoted'


# ============================================================================
#  Общие экземпляры типов SQLAlchemy (имя = имя PG-типа)
# ============================================================================

raw_item_status = Enum(RawItemStatus, name='raw_item_status')
stop_type = Enum(StopType, name='stop_type')
limit_scope = Enum(LimitScope, name='limit_scope')
limit_window = Enum(LimitWindow, name='limit_window')
norm_status = Enum(NormStatus, name='norm_status')
reject_reason_t = Enum(RejectReason, name='reject_reason_t')
priority_level = Enum(PriorityLevel, name='priority_level')
tonality_level = Enum(TonalityLevel, name='tonality_level')
delivery_mode = Enum(DeliveryMode, name='delivery_mode')
alert_status = Enum(AlertStatus, name='alert_status')
action_status = Enum(ActionStatus, name='action_status')
source_candidate_status = Enum(
    SourceCandidateStatus, name='source_candidate_status'
)
user_role = Enum(UserRole, name='user_role')
