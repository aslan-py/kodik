"""Антишум BP-2: агрегатный фильтр по topic_limit.

Решает проблему «один конкурент / источник / СМИ / регион занял весь отчёт»:
если уникальных событий в группе больше допустимого лимита — самые старые
помечаются как rejected(noise_limit).

Применяется ПОСЛЕ дедупа и вставки в normalized_item — именно потому, что:
  а) считаем уже уникальные события (не сырые копии);
  б) окно «неделя» включает строки из прошлых прогонов, которых нет в памяти.

Разрезы (scope):
  competitor — по competitor_id (один конкурент слишком часто упоминается)
  source     — по source_id     (один источник-парсер шумит)
  media      — по media_domain  (один сайт-публикатор доминирует)
  region     — по region_id     (один регион вытесняет остальные)

Окна (window):
  run  — только события, вставленные в текущем прогоне
  day  — за последние 24 часа
  week — за последние 7 дней
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import LimitScope, LimitWindow, NormStatus, RejectReason
from src.bp2.models import NormalizedItem, TopicLimit


def _since(window: LimitWindow, run_started_at: datetime) -> datetime:
    if window == LimitWindow.run:
        return run_started_at
    now = datetime.now(UTC)
    if window == LimitWindow.day:
        return now - timedelta(days=1)
    return now - timedelta(weeks=1)


_SCOPE_COL = {
    LimitScope.competitor: NormalizedItem.competitor_id,
    LimitScope.source: NormalizedItem.source_id,
    LimitScope.media: NormalizedItem.media_domain,
    LimitScope.region: NormalizedItem.region_id,
}


async def reject_over_limit(
    session: AsyncSession,
    limits: Sequence[TopicLimit],
    run_started_at: datetime,
) -> int:
    """Пометить rejected(noise_limit) всё сверх лимита по каждому правилу.

    Для каждого активного правила из topic_limit:
      - берём normalized_item со status=ok в нужном временном окне;
      - нумеруем строки внутри каждой группы (ROW_NUMBER DESC по created_at);
      - всё с номером > max_count → status=rejected, reject_reason=noise_limit.

    Самые СВЕЖИЕ события остаются (order DESC), самые старые отсекаются.
    Возвращает суммарное число обновлённых строк по всем правилам.
    """
    total = 0
    for limit in limits:
        col = _SCOPE_COL[limit.scope]
        since = _since(limit.window, run_started_at)

        rn = (
            func.row_number()
            .over(
                partition_by=col,
                order_by=NormalizedItem.created_at.desc(),
            )
            .label('rn')
        )

        subq = (
            select(NormalizedItem.id, rn)
            .where(NormalizedItem.status == NormStatus.ok)
            .where(col.is_not(None))
            .where(NormalizedItem.created_at >= since)
            .subquery()
        )

        stmt = (
            update(NormalizedItem)
            .where(
                NormalizedItem.id.in_(
                    select(subq.c.id).where(subq.c.rn > limit.max_count)
                )
            )
            .values(
                status=NormStatus.rejected,
                reject_reason=RejectReason.noise_limit,
            )
            .execution_options(synchronize_session=False)
        )

        result = await session.execute(stmt)
        total += result.rowcount

    return total
