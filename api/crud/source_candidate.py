"""Репозиторий source_candidate (BP-7) для API: только чтение.

Та же read-only форма, что и у api/crud/pipeline_view.py (get + list_all с
явными фильтрами), но в отдельном файле — это не BP-1/2/3/5, а BP-7.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import SourceCandidateStatus
from src.bp7.models import SourceCandidate


class SourceCandidateCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, item_id: int) -> SourceCandidate | None:
        return await self.session.get(SourceCandidate, item_id)

    async def list_all(
        self,
        status: SourceCandidateStatus | None = None,
        competitor_id: int | None = None,
        is_active: bool | None = None,
        domain: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[SourceCandidate]:
        stmt = select(SourceCandidate)
        if status is not None:
            stmt = stmt.where(SourceCandidate.status == status)
        if competitor_id is not None:
            stmt = stmt.where(SourceCandidate.competitor_id == competitor_id)
        if is_active is not None:
            stmt = stmt.where(SourceCandidate.is_active == is_active)
        if domain is not None:
            stmt = stmt.where(SourceCandidate.domain.ilike(f'%{domain}%'))
        stmt = (
            stmt.order_by(SourceCandidate.id.desc()).limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
