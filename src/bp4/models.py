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
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, Mixin, StrippedString
from src.bp1.models import RawItem
from src.bp3.models import CategorizedEvent


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
        StrippedString(512),
        comment='Заголовок',
    )
    media: Mapped[str | None] = mapped_column(
        StrippedString(256),
        comment='СМИ-публикатор (normalized_item.media_name)',
    )
    region: Mapped[str | None] = mapped_column(
        StrippedString(128),
        comment='Регион (region.name_display)',
    )
    macro_region: Mapped[str | None] = mapped_column(
        StrippedString(64),
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
        StrippedString(256),
        index=True,
        comment='Конкурент / объект (competitor.name)',
    )
    source_url: Mapped[str | None] = mapped_column(
        StrippedString(512),
        comment='Ссылка на событие (normalized_item.url)',
    )

    # ---- СМЫСЛЫ (денормализовано, готовые к показу строки) ----
    priority: Mapped[str] = mapped_column(
        StrippedString(8),
        index=True,
        comment='Приоритет П1..П4',
    )
    category: Mapped[str] = mapped_column(
        StrippedString(128),
        index=True,
        comment='Категория (category.name)',
    )
    tonality: Mapped[str] = mapped_column(
        StrippedString(32),
        comment='Тональность',
    )
    media_index: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        comment='Медиаиндекс',
    )
    action: Mapped[str | None] = mapped_column(
        StrippedString(512),
        comment='Требуемое действие',
    )
    deadline: Mapped[date | None] = mapped_column(
        Date,
        comment='Срок реакции',
    )
    department: Mapped[str | None] = mapped_column(
        StrippedString(128),
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
    alerted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment=(
            'Когда BP-5 последний раз проверял строку на значимость — '
            'НЕЗАВИСИМО от результата (даже если алерт не сработал). '
            'Отбор BP-5: alerted_at IS NULL OR updated_at > alerted_at. '
            'Не по журналу alert — там легитимны события с нулём алертов, '
            'и по нему нельзя было бы отличить «ещё не проверено» от '
            '«проверено, но не значимо»'
        ),
    )
    action_items_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment=(
            'Когда BP-6 перенёс задачи из categorized_event.task в '
            'action_item — НЕЗАВИСИМО от результата (даже если задач не '
            'было). Отбор BP-6: priority IN (П1, П2) AND '
            'action_items_generated_at IS NULL — БЕЗ реакции на updated_at '
            '(в отличие от alerted_at): повторная переразметка события не '
            'должна задвоить/переписать уже заведённые вручную action_item'
        ),
    )

    # Связи нужны админке (FastAdmin показывает FK только через relationship).
    # Ленивые по умолчанию: сериализация читает *_id, объект не трогает.
    categorized_event: Mapped['CategorizedEvent'] = relationship(
        'CategorizedEvent'
    )
    raw_item: Mapped['RawItem'] = relationship('RawItem')

    def __str__(self) -> str:
        return self.title

    __table_args__ = (
        CheckConstraint(
            'title = btrim(title)', name='ck_showcase_event_title_trimmed'
        ),
        CheckConstraint(
            'media = btrim(media)', name='ck_showcase_event_media_trimmed'
        ),
        CheckConstraint(
            'region = btrim(region)', name='ck_showcase_event_region_trimmed'
        ),
        CheckConstraint(
            'macro_region = btrim(macro_region)',
            name='ck_showcase_event_macro_region_trimmed',
        ),
        CheckConstraint(
            'competitor = btrim(competitor)',
            name='ck_showcase_event_competitor_trimmed',
        ),
        CheckConstraint(
            'source_url = btrim(source_url)',
            name='ck_showcase_event_source_url_trimmed',
        ),
        CheckConstraint(
            'priority = btrim(priority)',
            name='ck_showcase_event_priority_trimmed',
        ),
        CheckConstraint(
            'category = btrim(category)',
            name='ck_showcase_event_category_trimmed',
        ),
        CheckConstraint(
            'tonality = btrim(tonality)',
            name='ck_showcase_event_tonality_trimmed',
        ),
        CheckConstraint(
            'action = btrim(action)', name='ck_showcase_event_action_trimmed'
        ),
        CheckConstraint(
            'department = btrim(department)',
            name='ck_showcase_event_department_trimmed',
        ),
    )
