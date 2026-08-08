"""Модели BP-7 (агент расширения источников).

Админка BP-7 — это CRUD над УЖЕ существующими справочниками (competitor,
trigger, source, black_domain, stop_word, routing_rule, …) через FastAdmin
(код — api/admin/, инструкция — api/ADMIN_README.md), своих таблиц не
заводит. Единственная новая таблица процесса — очередь кандидатов
в источники.

- SourceCandidate: агент пишет кандидата с оценкой score. Когда score выше
  настраиваемого порога (core.config.settings.source_candidate_score_threshold,
  env SOURCE_CANDIDATE_SCORE_THRESHOLD), кандидат переносится в source —
  см. src/bp7/pipeline.py::SourceCandidatePromoter и src/bp7/BP7_README.md.
  status (new -> promoted) проставляется В МОМЕНТ переноса — так отбор на
  перенос идёт по индексу на status, без JOIN/NOT EXISTS с source на каждый
  прогон при росте таблицы. is_active (ActiveMixin) — можно снять с
  рассмотрения кандидата, не удаляя строку. Скрипт сидинга для неё не нужен —
  очередь наполняется агентом в рантайме (следующая итерация).

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import ActiveMixin, Base, Mixin, StrippedString
from core.enums import SourceCandidateStatus, source_candidate_status
from src.bp1.models import Competitor


class SourceCandidate(Base, Mixin, ActiveMixin):
    """Кандидаты в источники BP-7.

    Агент (следующая итерация) пишет строки с domain/url/competitor_id/score.
    UNIQUE на domain — не предлагать один и тот же источник дважды. Когда
    score строго больше порога — кандидат переносится в source (перенос см.
    src/bp7/pipeline.py). is_active=false исключает кандидата из переноса,
    не удаляя историю.
    """

    domain: Mapped[str] = mapped_column(
        StrippedString(256),
        unique=False,
        nullable=True,
        comment='Найденный домен-кандидат. UNIQUE — не предлагать дважды',
    )
    competitor_id: Mapped[int | None] = mapped_column(
        ForeignKey('competitor.id', ondelete='RESTRICT'),
        comment='По какому конкуренту/запросу нашли',
    )
    url: Mapped[str | None] = mapped_column(
        StrippedString(512),
        comment='Url найденного кандидата к парсингу',
    )
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        comment=(
            'Оценка релевантности от LLM (0.00–1.00). Кандидат переносится '
            'в source, когда score строго больше настраиваемого порога '
            '(core.config.settings.source_candidate_score_threshold)'
        ),
    )
    status: Mapped[SourceCandidateStatus] = mapped_column(
        source_candidate_status,
        default=SourceCandidateStatus.new,
        server_default=text("'new'"),
        comment=(
            'new -> promoted. Проставляется В МОМЕНТ переноса в source '
            '(SourceCandidatePromoter) — отбор кандидатов на перенос идёт '
            'по индексу на status, без JOIN/NOT EXISTS с source'
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Когда агент предложил кандидата',
    )

    # Связь нужна админке (FastAdmin показывает FK только через relationship).
    competitor: Mapped['Competitor | None'] = relationship('Competitor')

    def __str__(self) -> str:
        return self.domain

    __table_args__ = (
        CheckConstraint(
            'domain = btrim(domain)', name='ck_source_candidate_domain_trimmed'
        ),
        CheckConstraint(
            'url = btrim(url)',
            name='ck_source_candidate_url_trimmed',
        ),
        CheckConstraint(
            'score IS NULL OR (score BETWEEN 0 AND 1)',
            name='ck_source_candidate_score_range',
        ),
        Index('ix_source_candidate_status', 'status'),
    )
