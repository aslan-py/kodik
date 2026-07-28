"""Модели BP-7 (агент расширения источников).

Админка BP-7 — это CRUD над УЖЕ существующими справочниками (competitor,
trigger, source, black_domain, stop_word, routing_rule, …) через SQLAdmin,
своих таблиц не заводит. Единственная новая таблица процесса — очередь
модерации предложенных источников.

- SourceCandidate: агент пишет pending, человек в админке approve/reject.
  При approve домен уходит в source. Автоподключения нет — только через
  модерацию (правило ТЗ). Скрипт сидинга для неё не нужен — очередь
  наполняется агентом в рантайме.

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, Mixin
from core.enums import CandidateStatus, candidate_status


class SourceCandidate(Base, Mixin):
    """Очередь модерации источников BP-7.

    Агент пишет pending (шаг 6), человек в админке approve/reject (шаг 7).
    При approve домен уходит в source (шаг 8), следующий цикл его парсит.
    UNIQUE на domain — не предлагать один и тот же источник дважды.
    """

    domain: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        comment='Найденный домен-кандидат. UNIQUE — не предлагать дважды',
    )
    competitor_id: Mapped[int | None] = mapped_column(
        ForeignKey('competitor.id', ondelete='RESTRICT'),
        comment='По какому конкуренту/запросу нашли',
    )
    evidence_url: Mapped[str | None] = mapped_column(
        String(512),
        comment='Ссылка-доказательство: где упомянут конкурент',
    )
    llm_assessment: Mapped[str | None] = mapped_column(
        Text,
        comment='Краткая оценка LLM: что за ресурс, релевантность, публичность',
    )
    status: Mapped[CandidateStatus] = mapped_column(
        candidate_status,
        default=CandidateStatus.pending,
        server_default=text("'pending'"),
        comment='pending → approved / rejected',
    )
    moderated_by: Mapped[str | None] = mapped_column(
        String(128),
        comment='Кто промодерировал',
    )
    moderated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment='Когда промодерировали',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Когда агент предложил',
    )
