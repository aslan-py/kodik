"""Модели BP-2 (нормализация, дедупликация, фильтрация шума).

Справочники фильтрации:
- Region: нормализация сырых географических названий
- BlackDomain: домены-публикаторы в чёрном списке
- StopWord: стоп-слова, стоп-темы и ложные срабатывания
- TopicLimit: лимиты анти-шума (агрегатный фильтр)

Выход:
- NormalizedItem: silver-слой, один объект из raw_data.items[] — одна строка.
  Содержит только ФАКТЫ (дата, заголовок, источник, регион, конкурент).
  Смыслы (приоритет, категория, тональность) добавляет BP-3
  в categorized_event.

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

import enum
from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActiveMixin, Base, Mixin

# ============================================================================
#  Enums
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
#  Справочники BP-2
# ============================================================================


class Region(Base, Mixin):
    """Справочник регионов.

    Одна строка = один реальный город/регион. Каноническое имя — name_display.
    Все варианты написания («г. Волгоград», «волгоград», «г волгоград») лежат
    в массиве name_aliases в нижнем регистре.

    Lookup при нормализации:
        SELECT * FROM region WHERE lower(:raw) = ANY(name_aliases)
    GIN-индекс делает этот запрос быстрым даже на тысячах городов.
    """

    name_display: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        comment=(
            'Каноническое имя для витрины и карты: «Волгоград». '
            'По нему группируем в дашборде'
        ),
    )
    name_aliases: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        comment=(
            'Варианты написания в нижнем регистре: '
            '[«волгоград», «г. волгоград», «г волгоград»]'
        ),
    )
    macro_region: Mapped[str | None] = mapped_column(
        String(64),
        comment='Федеральный округ: ЦФО, ЮФО — для карты рынка',
    )
    latitude: Mapped[float | None] = mapped_column(
        Float,
        comment='Широта центра региона (WGS-84), для карты рынка',
    )
    longitude: Mapped[float | None] = mapped_column(
        Float,
        comment='Долгота центра региона (WGS-84), для карты рынка',
    )

    __table_args__ = (
        Index(
            'ix_region_name_aliases',
            'name_aliases',
            postgresql_using='gin',
        ),
    )


class BlackDomain(Base, Mixin, ActiveMixin):
    """Чёрный список доменов-публикаторов.

    Домены СМИ, которые отсеиваем целиком: заказные, компрометирующие.
    Проверяется по media_domain события (urlparse(url).netloc).
    """

    domain: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        comment=(
            'Домен публикатора новости (напр. kompromat.ru). '
            'НЕ source — то, откуда пришёл контент'
        ),
    )
    reason: Mapped[str | None] = mapped_column(
        String(512),
        comment='Почему в списке: заказной / компрометирующий ресурс',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Время добавления домена в чёрный список',
    )


class StopWord(Base, Mixin, ActiveMixin):
    """Стоп-слова, стоп-темы и ложные срабатывания.

    Универсальная таблица фильтрации по типу. Проверяются поля
    title и text события (lowercase, вхождение подстроки).
    Тип определяет reject_reason в normalized_item.
    """

    phrase: Mapped[str] = mapped_column(
        String(512),
        comment=(
            'Слово или фраза для отсева (проверяется вхождением в title/text)'
        ),
    )
    type: Mapped[StopType] = mapped_column(
        Enum(StopType, name='stop_type'),
        comment=(
            'stop_word — стоп-слово; stop_topic — стоп-тема; '
            'false_positive — ложное срабатывание'
        ),
    )
    note: Mapped[str | None] = mapped_column(
        String(512),
        comment='Пояснение для аналитика: почему добавили и от чего защищает',
    )

    __table_args__ = (
        UniqueConstraint('phrase', 'type', name='uq_stop_word_phrase_type'),
    )


class TopicLimit(Base, Mixin, ActiveMixin):
    """Лимиты анти-шума (агрегатный фильтр).

    Задаёт максимум событий на одну группу за временное окно.
    Всё сверх лимита (самые старые в группе) получает
    status='rejected', reject_reason='noise_limit'.
    Применяется ПОСЛЕ дедупа и вставки (считаем уже уникальные строки в БД).
    """

    scope: Mapped[LimitScope] = mapped_column(
        Enum(LimitScope, name='limit_scope'),
        comment=(
            'По какой группе считаем долю: competitor / source / media / region'
        ),
    )
    max_count: Mapped[int] = mapped_column(
        Integer,
        comment=(
            'Максимум событий на одну группу за окно; '
            'сверх — rejected(noise_limit)'
        ),
    )
    window: Mapped[LimitWindow] = mapped_column(
        Enum(LimitWindow, name='limit_window'),
        default=LimitWindow.week,
        server_default=sa_text("'week'"),
        comment='Окно подсчёта: run — один прогон, day — сутки, week — неделя',
    )
    note: Mapped[str | None] = mapped_column(
        String(512),
        comment='Напр.: «СКС занимает ~40% отчёта 5 недель подряд»',
    )


# ============================================================================
#  Выход BP-2 — нормализованные события (silver-слой)
# ============================================================================


class NormalizedItem(Base, Mixin):
    """Нормализованные события — silver-слой BP-2.

    Один объект из raw_data.items[] → одна строка. Содержит только ФАКТЫ
    (дата, заголовок, источник, регион, конкурент, url, тело).
    Смыслы (приоритет, категория, тональность) добавляет BP-3
    в categorized_event.

    status=ok → идут в BP-3; status=rejected → лежат помеченными, не удаляем.
    Отсеянное не удаляем — аналитик разбирает отсев и настраивает правила.

    dedup_key — хэш бизнес-полей (конкурент+заголовок+регион+дата).
    UNIQUE на dedup_key реализует дедупликацию через INSERT … ON CONFLICT.
    """

    raw_item_id: Mapped[int] = mapped_column(
        ForeignKey('raw_item.id', ondelete='RESTRICT'),
        comment=(
            'Ссылка назад на сырьё (drill-down, требование прозрачности ТЗ)'
        ),
    )
    competitor_id: Mapped[int | None] = mapped_column(
        ForeignKey('competitor.id', ondelete='RESTRICT'),
        comment='Конкурент. NULL если из текста однозначно не вытащили',
    )
    region_id: Mapped[int | None] = mapped_column(
        ForeignKey('region.id', ondelete='RESTRICT'),
        comment='Регион после lookup в region. NULL если не определён',
    )
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey('source.id', ondelete='RESTRICT'),
        comment=(
            'Источник. Денормализовано из raw_item→search_task→source, '
            'чтобы не джойнить в два прыжка'
        ),
    )

    published_at: Mapped[date | None] = mapped_column(
        Date,
        comment=(
            'Дата события, нормализована к ISO '
            'из сырой строки (напр. «18 июля 2026»)'
        ),
    )
    title: Mapped[str] = mapped_column(
        String(512),
        comment='Заголовок события',
    )
    media_name: Mapped[str | None] = mapped_column(
        String(256),
        comment=(
            'СМИ-публикатор: «Big-news.ru, Москва». '
            'NULL для источников без публикатора (напр. hh.ru)'
        ),
    )
    media_domain: Mapped[str | None] = mapped_column(
        String(256),
        comment='Домен публикатора — для сверки с black_domain',
    )
    url: Mapped[str | None] = mapped_column(
        String(512),
        comment='Ссылка на конкретное событие (НЕ запрос парсера)',
    )
    text: Mapped[str | None] = mapped_column(
        Text,
        comment=(
            'Тело события. Вход для стоп-слов в BP-2 и для промпта LLM в BP-3'
        ),
    )
    extra: Mapped[dict | None] = mapped_column(
        JSONB,
        comment=(
            'Источник-специфичные факты: '
            '{salary_from, salary_to, currency} для вакансий'
        ),
    )

    dedup_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        comment=(
            'Хэш бизнес-полей (конкурент|заголовок|дата|регион). '
            'UNIQUE = дедуп через ON CONFLICT'
        ),
    )
    status: Mapped[NormStatus] = mapped_column(
        Enum(NormStatus, name='norm_status'),
        default=NormStatus.ok,
        server_default=sa_text("'ok'"),
        comment='ok → идут в BP-3; rejected → помечены, не удаляем',
    )
    reject_reason: Mapped[RejectReason | None] = mapped_column(
        Enum(RejectReason, name='reject_reason_t'),
        comment='Причина отсева. NULL для status=ok',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Время нормализации события',
    )
