"""Модели BP-4 (витрина данных под BI, слой представления).

Выход:
- ShowcaseEvent: плоская денормализованная витрина. Одно событие = одна
  широкая строка. id из слоёв заменены на читаемые ИМЕНА через справочники,
  поэтому BI читает без джойнов. Это ровно строка целевого xlsx-отчёта.

Ключ для инкрементального UPSERT — categorized_event_id (одна строка витрины
на размеченное событие). raw_item_id обеспечивает drill-down к исходнику
(требование прозрачности ТЗ).

На демо витрина может быть VIEW; здесь — физическая таблица под прод
(быстро для BI, можно индексировать, стабильный контракт колонок).

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, Mixin


class ShowcaseEvent(Base, Mixin):
    """Плоская витрина BP-4 под BI.

    Денормализована: id из слоёв заменены на читаемые имена через
    справочники (region_id → «Калуга», category_id → «PR-активность»).
    Приоритет/категория/тональность здесь — строки, а не enum: витрина
    отдаёт готовые к показу значения, а не коды.

    index=True на published_at / competitor / priority / category — под
    типовые фильтры дашборда: лента по датам, паспорт конкурента, срезы
    по приоритетам и категориям.
    """

    categorized_event_id: Mapped[int] = mapped_column(
        ForeignKey('categorized_event.id', ondelete='RESTRICT'),
        unique=True,
        comment=(
            'Ключ инкрементального UPSERT: одна строка витрины '
            'на размеченное событие'
        ),
    )
    raw_item_id: Mapped[int] = mapped_column(
        ForeignKey('raw_item.id', ondelete='RESTRICT'),
        comment='Drill-down до сырья (из строки витрины → к исходнику)',
    )

    # ---- ФАКТЫ (денормализовано: id заменены на имена через справочники) ----
    published_at: Mapped[date | None] = mapped_column(
        Date,
        index=True,
        comment='Дата события',
    )
    title: Mapped[str] = mapped_column(
        String(512),
        comment='Заголовок',
    )
    media: Mapped[str | None] = mapped_column(
        String(256),
        comment='СМИ-публикатор (normalized_item.media_name)',
    )
    region: Mapped[str | None] = mapped_column(
        String(128),
        comment='Регион (region.name_display)',
    )
    macro_region: Mapped[str | None] = mapped_column(
        String(64),
        comment='Федеральный округ (region.macro_region)',
    )
    latitude: Mapped[float | None] = mapped_column(
        Float,
        comment='Широта центра региона (WGS-84) — метка на карте рынка',
    )
    longitude: Mapped[float | None] = mapped_column(
        Float,
        comment='Долгота центра региона (WGS-84) — метка на карте рынка',
    )
    competitor: Mapped[str | None] = mapped_column(
        String(256),
        index=True,
        comment='Конкурент / объект (competitor.name)',
    )
    source_url: Mapped[str | None] = mapped_column(
        String(512),
        comment='Ссылка на событие (normalized_item.url)',
    )

    # ---- СМЫСЛЫ (денормализовано, готовые к показу строки) ----
    priority: Mapped[str] = mapped_column(
        String(8),
        index=True,
        comment='Приоритет П1..П4',
    )
    category: Mapped[str] = mapped_column(
        String(128),
        index=True,
        comment='Категория (category.name)',
    )
    tonality: Mapped[str] = mapped_column(
        String(32),
        comment='Тональность',
    )
    media_index: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        comment='Медиаиндекс',
    )
    action: Mapped[str | None] = mapped_column(
        String(512),
        comment='Требуемое действие',
    )
    deadline: Mapped[date | None] = mapped_column(
        Date,
        comment='Срок реакции',
    )
    department: Mapped[str | None] = mapped_column(
        String(128),
        comment='Ответственный отдел (department.name)',
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        comment='Комментарий',
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Инкрементальный UPSERT, без полной перезагрузки',
    )
