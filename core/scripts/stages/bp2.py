"""Этап BP-2: нормализованные события (normalized_item) — ФАКТЫ.

Кладёт готовый silver-слой, минуя конвейер очистки. Нужен, когда работаешь
со СЛЕДУЮЩИМ процессом (BP-3 или витриной) и не хочешь каждый раз гонять
BP-2: залил факты одной командой и занимаешься разметкой.

Запуск:
    python -m core.scripts.stages.bp2

Альтернатива — получить те же факты по-настоящему, из сырья:
    python -m core.scripts.stages.bp1
    python -c "import asyncio; from src.bp2.pipeline import run_bp2; \\
               print(asyncio.run(run_bp2()))"

Набор берётся из демо-новостей (stages/news_data.py) — того же CSV, из
которого этап BP-1 собирает сырьё, только здесь тексты кладутся НАЧИСТО:
как их отдал бы конвейер очистки. Колонка reject задаёт исход фильтров, и
в наборе есть строка на КАЖДУЮ причину отсева — чтобы было видно, как
выглядит отбракованное и что оно не уходит дальше по конвейеру. Плюс
событие без региона: region_id = NULL проверяет, что LEFT JOIN в витрине
не роняет сборку.

Требует залитых справочников (stages/dictionaries) и сырья (stages/bp1):
каждая строка ссылается на raw_item — это drill-down до исходника.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import NormStatus
from core.scripts.stages.cascade import clear_from
from core.scripts.stages.news_data import NEWS
from src.bp1.models import Competitor, RawItem, SearchTask, Source
from src.bp2.dedup import make_dedup_key
from src.bp2.models import NormalizedItem, Region
from src.bp2.schemas import TITLE_PLACEHOLDER, domain_from_url

# ============================================================================
#  Этап
# ============================================================================


async def seed(session: AsyncSession) -> int:
    """Залить нормализованные события.

    Каждая строка привязывается к первому НЕ-error снимку своего конкурента
    (drill-down до сырья). dedup_key считается той же формулой, что и в
    конвейере — make_dedup_key из src/bp2/dedup.py, чтобы фабрикованные
    строки и настоящий прогон BP-2 не создавали дублей друг для друга.
    """
    competitors = {
        c.name: c.id
        for c in (await session.execute(select(Competitor))).scalars()
    }
    regions = {
        r.name_display: r.id
        for r in (await session.execute(select(Region))).scalars()
    }
    source_id = await session.scalar(select(Source.id).limit(1))

    # первый успешный снимок каждого конкурента
    raw_by_competitor: dict[int, int] = {}
    rows = await session.execute(
        select(SearchTask.competitor_id, RawItem.id)
        .join(RawItem, RawItem.search_task_id == SearchTask.id)
        .where(RawItem.raw_data.is_not(None))
        .order_by(RawItem.id)
    )
    for competitor_id, raw_id in rows:
        raw_by_competitor.setdefault(competitor_id, raw_id)

    if not raw_by_competitor:
        raise RuntimeError(
            'Нет сырья — не к чему привязать факты. '
            'Сначала: python -m core.scripts.stages.bp1'
        )

    added = 0
    for news in NEWS:
        competitor_id = competitors.get(news.competitor)
        raw_item_id = raw_by_competitor.get(competitor_id)
        if raw_item_id is None:
            continue
        session.add(
            NormalizedItem(
                raw_item_id=raw_item_id,
                competitor_id=competitor_id,
                region_id=regions.get(news.region),
                source_id=source_id,
                published_at=news.published_at,
                # У события с parse_error заголовка нет — в БД он NOT NULL,
                # поэтому кладём ту же заглушку, что подставляет схема BP-2.
                title=news.title or TITLE_PLACEHOLDER,
                media_name=news.media_name,
                media_domain=domain_from_url(news.url),
                url=news.url,
                text=news.text,
                extra=None,
                dedup_key=make_dedup_key(
                    news.competitor,
                    news.title or TITLE_PLACEHOLDER,
                    news.published_at.isoformat(),
                    news.region,
                ),
                status=NormStatus.ok if news.is_clean else NormStatus.rejected,
                reject_reason=news.reject,
            )
        )
        added += 1

    await session.flush()
    return added


async def clear(session: AsyncSession) -> int:
    """Снести факты и всё, что на них построено (разметку, витрину, алерты)."""
    return await clear_from(session, NormalizedItem)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-2 (таблица normalized_item)', clear, seed)
