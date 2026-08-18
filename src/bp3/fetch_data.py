from sqlalchemy import and_, exists, func, not_, select

from src.bp1.models import Competitor, Source
from src.bp2.models import NormalizedItem
from src.bp3.db import AsyncSessionLocal
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp7.models import SourceCandidate


async def fetch_data():
    async with AsyncSessionLocal() as session:
        stmt_items = select(NormalizedItem.id, NormalizedItem.text).where(
            and_(
                NormalizedItem.status == 'ok',
                not_(
                    exists().where(
                        CategorizedEvent.normalized_item_id == NormalizedItem.id
                    )
                ),
            )
        )

        rows_items = (await session.execute(stmt_items)).mappings().all()
        news_list = [
            {'id': row['id'], 'text': row['text']} for row in rows_items
        ]

        stmt_cat = select(Category.name, Category.note)
        rows_cat = (await session.execute(stmt_cat)).mappings().all()
        cat_list = [{row['name']: row['note']} for row in rows_cat]

        stmt_dep = select(Department.name, Department.note)
        rows_dep = (await session.execute(stmt_dep)).mappings().all()
        depart_list = [{row['name']: row['note']} for row in rows_dep]

    return news_list, cat_list, depart_list


async def fetch_news_stats():
    async with AsyncSessionLocal() as session:
        stmt = (
            select(
                NormalizedItem.competitor_id,
                func.count().label('news_count'),
                func.count(func.distinct(NormalizedItem.source_id)).label(
                    'source_count'
                ),
            )
            .where(
                and_(
                    NormalizedItem.status == 'ok',
                    not_(
                        exists().where(
                            CategorizedEvent.normalized_item_id
                            == NormalizedItem.id
                        )
                    ),
                )
            )
            .group_by(NormalizedItem.competitor_id)
        )

        rows = (await session.execute(stmt)).mappings().all()
        news_stats = {
            row['competitor_id']: {
                'news_count': row['news_count'],
                'source_count': row['source_count'],
            }
            for row in rows
        }

        stmt_sources = select(func.count(func.distinct(Source.id))).where(
            Source.is_active.is_(True)
        )
        count_sources = await session.scalar(stmt_sources)

    return news_stats, count_sources


async def fetch_seed_urls():
    async with AsyncSessionLocal() as session:
        stmt_sources = select(func.distinct(Source.name)).where(
            Source.is_active.is_(True)
        )
        list_urls = (await session.execute(stmt_sources)).scalars().all()

        stmt_domains = select(func.distinct(SourceCandidate.domain))
        unique_domains = (await session.execute(stmt_domains)).scalars().all()

        stmt_competitor = select(Competitor.id, Competitor.name)
        rows_compt = (await session.execute(stmt_competitor)).mappings().all()
        compt_list = [{row['id']: row['name']} for row in rows_compt]

    return list_urls, unique_domains, compt_list
