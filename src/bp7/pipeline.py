"""Перенос BP-7: source_candidate -> source по порогу score.

Кандидат переносится в source, когда его score строго больше настраиваемого
порога (core.config.settings.source_candidate_score_threshold, env
SOURCE_CANDIDATE_SCORE_THRESHOLD) — порог живёт в конфиге, не в коде, его
можно поменять без деплоя новой логики.

Логика собрана в класс (SourceCandidatePromoter), а не в свободные функции
(в отличие от src/bp4/pipeline.py, src/bp5/pipeline.py) — так её позже
обернут декоратором Celery без переписывания, когда в проекте появится общая
настройка очередей (см. src/bp7/BP7_README.md, "Осознанно не реализовано").
Сейчас, как и у остальных BP, обвязки Celery нет — оркестратор
(run_bp7_promotion) вызывается напрямую.

Отбор кандидатов на перенос идёт по SourceCandidate.status == 'new'
(индексированное поле, ix_source_candidate_status) — не JOIN/NOT EXISTS
с source на каждый прогон: при росте таблицы такая сверка стала бы дорогой.
В момент переноса status меняется на 'promoted', поэтому повторный прогон
эту строку уже не пересматривает.

Дополнительно source.name = candidate.domain пишется через INSERT ... ON
CONFLICT DO NOTHING (domain гарантированно NOT NULL/unique, в отличие от
url) — второй уровень защиты от дублей на случай, если source уже содержит
такое имя не через этот перенос.
"""

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import AsyncSessionLocal
from core.enums import SourceCandidateStatus
from src.bp1.models import Source
from src.bp7.models import SourceCandidate


class SourceCandidatePromoter:
    """Переносит source_candidate -> source по настраиваемому порогу score."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def get_threshold(self) -> Decimal:
        """Текущий порог из конфига (.env), Decimal — для сравнения со score."""
        return Decimal(str(settings.source_candidate_score_threshold))

    async def select_promotable(
        self, threshold: Decimal
    ) -> Sequence[SourceCandidate]:
        """Активные new-кандидаты со score строго больше порога.

        Фильтр по status == new (индекс ix_source_candidate_status) —
        уже перенесённые (promoted) в выборку не попадают, таблицу заново
        не пересматриваем.
        """
        stmt = select(SourceCandidate).where(
            SourceCandidate.is_active.is_(True),
            SourceCandidate.status == SourceCandidateStatus.new,
            SourceCandidate.score.is_not(None),
            SourceCandidate.score > threshold,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def promote(self) -> dict:
        """Прогон переноса: порог -> отбор -> source -> status=promoted.

        Пишет ТОЛЬКО в переданной сессии (flush, без commit) — коммитит
        вызывающий код (run_bp7_promotion или чужая транзакция, как у
        src/bp5/pipeline.py::sync_alerts).
        """
        threshold = self.get_threshold()
        candidates = await self.select_promotable(threshold)
        if not candidates:
            return {
                'threshold': float(threshold),
                'checked': 0,
                'promoted': 0,
            }

        rows = [{'name': c.domain, 'is_active': True} for c in candidates]
        stmt = pg_insert(Source).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=['name'])
        result = await self.session.execute(stmt)

        # Помечаем ВСЕ отобранные кандидаты как promoted, даже если конкретную
        # строку в source ON CONFLICT DO NOTHING пропустил (source уже
        # содержал такое имя) — с точки зрения source_candidate попытка
        # переноса совершена, второй раз его пересматривать не нужно.
        candidate_ids = [c.id for c in candidates]
        await self.session.execute(
            update(SourceCandidate)
            .where(SourceCandidate.id.in_(candidate_ids))
            .values(status=SourceCandidateStatus.promoted)
        )
        await self.session.flush()

        return {
            'threshold': float(threshold),
            'checked': len(candidates),
            'promoted': result.rowcount,
        }


async def run_bp7_promotion() -> dict:
    """Один самостоятельный прогон переноса: своя сессия + commit.

    Точка входа для ручного запуска (см. src/bp7/BP7_README.md) и для
    будущей Celery-задачи (обернуть декоратором, вызвать этот же метод).
    """
    async with AsyncSessionLocal() as session:
        summary = await SourceCandidatePromoter(session).promote()
        await session.commit()
        return summary


if __name__ == '__main__':
    import asyncio

    result = asyncio.run(run_bp7_promotion())
    print(result)
