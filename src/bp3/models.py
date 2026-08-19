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
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import ActiveMixin, Base, Mixin, StrippedString
from core.enums import (
    PriorityLevel,
    TonalityLevel,
    priority_level,
    tonality_level,
)
from src.bp2.models import NormalizedItem

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
        StrippedString(128),
        unique=True,
        comment=(
            'Категория события (напр. надзорная санкция и юр.риск, '
            'PR-активность конкурента, репутационный риск)'
        ),
    )
    note: Mapped[str | None] = mapped_column(
        StrippedString(512),
        comment='Определение категории для аналитика: что под неё подпадает',
    )

    def __str__(self) -> str:
        """Строковое представление для админки — название категории."""
        return self.name

    __table_args__ = (
        CheckConstraint('name = btrim(name)', name='ck_category_name_trimmed'),
        CheckConstraint('note = btrim(note)', name='ck_category_note_trimmed'),
    )


class Department(Base, Mixin, ActiveMixin):
    """Справочник отделов (маршрутизация ответственного).

    Отделы заказчика, на которые LLM (в BP-3) и матрица маршрутизации
    (в BP-5) назначают ответственного за событие.
    """

    name: Mapped[str] = mapped_column(
        StrippedString(128),
        unique=True,
        comment='Отдел: PR, Юристы, Аналитика, Маркетинг',
    )
    note: Mapped[str | None] = mapped_column(
        StrippedString(512),
        comment='Зона ответственности отдела: какие категории он ведёт',
    )

    def __str__(self) -> str:
        """Строковое представление для админки — название отдела."""
        return self.name

    __table_args__ = (
        CheckConstraint(
            'name = btrim(name)', name='ck_department_name_trimmed'
        ),
        CheckConstraint(
            'note = btrim(note)', name='ck_department_note_trimmed'
        ),
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
        StrippedString(512),
        comment='Требуемое действие (черновик от LLM)',
    )
    task: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        comment=(
            'Список конкретных задач от LLM (GenerationTaskModule): '
            '1-3 практических шага по реализации action'
        ),
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
        StrippedString(512),
        comment='Комментарий от LLM',
    )
    expected_result: Mapped[str | None] = mapped_column(
        Text,
        comment=(
            'Ожидаемый результат по событию. Источника в BP-3 пока нет — '
            'заполняется NULL, задел под будущий LLM-модуль'
        ),
    )

    llm_model: Mapped[str | None] = mapped_column(
        StrippedString(64),
        comment='Какая модель разметила (для аудита)',
    )
    prompt_version: Mapped[str | None] = mapped_column(
        StrippedString(32),
        comment='Версия промпта/правил (для перекатегоризации)',
    )
    categorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        index=True,
        comment=(
            'Когда разметили (INSERT) или переразметили (UPDATE). '
            'По индексу BP-4 отбирает переразмеченные события '
            '(categorized_at > showcase_event.updated_at). onupdate '
            'срабатывает автоматически на ЛЮБОМ UPDATE через SQLAlchemy '
            '(и точечная правка атрибута, и bulk update()) — колонка не '
            'перечислена в .values(), компилятор сам подставит значение. '
            'НЕ сработает при INSERT ... ON CONFLICT DO UPDATE (это '
            'технически INSERT, не UPDATE) и при правке в обход '
            'SQLAlchemy — сырой SQL, DBeaver, pgAdmin: там колонку нужно '
            'проставлять руками'
        ),
    )

    # Связи нужны админке (FastAdmin показывает FK только через relationship).
    # Ленивые по умолчанию: сериализация читает *_id, объект не трогает.
    normalized_item: Mapped['NormalizedItem'] = relationship('NormalizedItem')
    category: Mapped['Category'] = relationship('Category')
    department: Mapped['Department | None'] = relationship('Department')

    def __str__(self) -> str:
        """Строковое представление для админки — id и приоритет события."""
        return f'#{self.id} · {self.priority}'

    __table_args__ = (
        CheckConstraint(
            'action = btrim(action)',
            name='ck_categorized_event_action_trimmed',
        ),
        CheckConstraint(
            'comment = btrim(comment)',
            name='ck_categorized_event_comment_trimmed',
        ),
        CheckConstraint(
            'llm_model = btrim(llm_model)',
            name='ck_categorized_event_llm_model_trimmed',
        ),
        CheckConstraint(
            'prompt_version = btrim(prompt_version)',
            name='ck_categorized_event_prompt_version_trimmed',
        ),
    )
