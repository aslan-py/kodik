"""Модели BP-3 (LLM-категоризация, gold-слой).

Справочники разметки:
- Category: контролируемый словарь категорий событий (вход для LLM)
- Department: отделы-получатели (маршрутизация ответственного)

Выход:
- CategorizedEvent: gold-слой, СМЫСЛЫ события (приоритет, категория,
  тональность, действие, срок, отдел, комментарий). 1:1 к NormalizedItem
  через UNIQUE на normalized_item_id. Факты берутся из NormalizedItem по FK,
  перекатегоризация = UPDATE этой строки, факты не трогаются.

Enum'ы priority_level и tonality_level объявлены здесь (их зона — BP-3),
но переиспользуются в BP-5 (routing_rule, alert) — импортируются оттуда.

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import ActiveMixin, Base, Mixin
from core.enums import (
    PriorityLevel,
    TonalityLevel,
    priority_level,
    tonality_level,
)

# ============================================================================
#  Справочники BP-3
# ============================================================================


class Category(Base, Mixin, ActiveMixin):
    """Справочник категорий событий (контролируемый словарь для LLM).

    Закрытый список категорий из ТЗ: надзорная санкция и юр.риск;
    репутационный риск; PR-активность; системная проблема; признание
    качества; косвенное упоминание; инфошум. LLM возвращает название,
    код делает lookup и получает id (отсебятину ловим на валидации).
    """

    name: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        comment=(
            'Категория события (напр. надзорная санкция и юр.риск, '
            'PR-активность конкурента, репутационный риск)'
        ),
    )


class Department(Base, Mixin, ActiveMixin):
    """Справочник отделов (маршрутизация ответственного).

    Отделы заказчика, на которые LLM (в BP-3) и матрица маршрутизации
    (в BP-5) назначают ответственного за событие.
    """

    name: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        comment='Отдел: PR, Тендеры, Юристы, Аналитика, Маркетинг',
    )


# ============================================================================
#  Выход BP-3 — размеченные события (gold-слой)
# ============================================================================


class CategorizedEvent(Base, Mixin):
    """Результат LLM-категоризации — СМЫСЛЫ события (gold-слой BP-3).

    Одна строка фактов (NormalizedItem) ↔ одна строка разметки. UNIQUE на
    normalized_item_id гарантирует связь 1:1. Факты (дата, заголовок,
    источник) не дублируются — берутся по FK. Перекатегоризация меняет
    только эту строку.

    Гоним через LLM только status=ok и только некатегоризированные события.
    priority и deadline: LLM даёт приоритет, срок код считает сам
    (П1 = дата+48ч, П2 = +7 дней). category_id/department_id: LLM даёт
    название → код ищет id. media_index приходит из агрегатора, не от LLM.
    """

    normalized_item_id: Mapped[int] = mapped_column(
        ForeignKey('normalized_item.id', ondelete='RESTRICT'),
        unique=True,
        comment='1:1 ссылка на факты события. UNIQUE = одна разметка',
    )

    priority: Mapped[PriorityLevel] = mapped_column(
        priority_level,
        comment='Приоритет П1–П4 (от LLM)',
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey('category.id', ondelete='RESTRICT'),
        comment='Категория события из справочника (LLM → lookup id)',
    )
    tonality: Mapped[TonalityLevel] = mapped_column(
        tonality_level,
        comment='Тональность (от LLM)',
    )
    media_index: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        comment=(
            'Медиаиндекс (охват/заметность) из лицензионного агрегатора. '
            'НЕ выход LLM. NULL если источника нет'
        ),
    )
    action: Mapped[str | None] = mapped_column(
        String(512),
        comment='Требуемое действие (черновик от LLM)',
    )
    deadline: Mapped[date | None] = mapped_column(
        Date,
        comment='Срок реакции. Считает код: П1 = дата+48ч, П2 = +7 дней',
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey('department.id', ondelete='RESTRICT'),
        comment='Ответственный отдел (LLM → lookup id)',
    )
    comment: Mapped[str | None] = mapped_column(
        String(512),
        comment='Комментарий от LLM',
    )

    llm_model: Mapped[str | None] = mapped_column(
        String(64),
        comment='Какая модель разметила (для аудита)',
    )
    prompt_version: Mapped[str | None] = mapped_column(
        String(32),
        comment='Версия промпта/правил (для перекатегоризации)',
    )
    categorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Когда разметили',
    )
