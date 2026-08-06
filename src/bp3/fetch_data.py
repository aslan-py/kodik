import os

from dotenv import load_dotenv
from sqlalchemy import and_, create_engine, exists, func, not_, select
from sqlalchemy.orm import sessionmaker

from src.bp1.models import Competitor, Source
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp7.models import SourceCandidate

load_dotenv()
DATABASE_URL = (
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}'
    f'@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)


engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def fetch_data():
    with Session() as session:
        stmt_items = (
            select(NormalizedItem.id, NormalizedItem.text)
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
            .limit(10)
        )

        rows_items = session.execute(stmt_items).mappings().all()
        news_list = [
            {'id': row['id'], 'text': row['text']} for row in rows_items
        ]

        stmt_cat = select(Category.name, Category.note)
        rows_cat = session.execute(stmt_cat).mappings().all()
        cat_list = [{row['name']: row['note']} for row in rows_cat]

        stmt_dep = select(Department.name, Department.note)
        rows_dep = session.execute(stmt_dep).mappings().all()
        depart_list = [{row['name']: row['note']} for row in rows_dep]

    return news_list, cat_list, depart_list


def fetch_news_stats():
    with Session() as session:
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

        rows = session.execute(stmt).mappings().all()
        news_stats = {
            row['competitor_id']: {
                'news_count': row['news_count'],
                'source_count': row['source_count'],
            }
            for row in rows
        }

        stmt_sources = select(func.count(func.distinct(Source.id))).where(
            Source.is_active == 'True'
        )
        count_sources = session.execute(stmt_sources).scalar()

    return news_stats, count_sources


def fetch_seed_urls():
    with Session() as session:
        stmt_sources = select(func.distinct(Source.name)).where(
            Source.is_active == 'True'
        )
        list_urls = session.execute(stmt_sources).scalars().all()

        stmt_sources = select(func.distinct(SourceCandidate.domain))
        unique_domains = session.execute(stmt_sources).scalars().all()

        stmt_competitor = select(Competitor.id, Competitor.name)
        rows_compt = session.execute(stmt_competitor).mappings().all()
        compt_list = [{row['id']: row['name']} for row in rows_compt]

    return list_urls, unique_domains, compt_list
