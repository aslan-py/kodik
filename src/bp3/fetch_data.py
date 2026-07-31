import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, exists, not_, select
from sqlalchemy.orm import sessionmaker

from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department

load_dotenv()
DATABASE_URL = (
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}'
    f'@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)


engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def fetch_data():
    with Session() as session:
        stmt_items = select(NormalizedItem.id, NormalizedItem.text).where(
            not_(
                exists().where(
                    CategorizedEvent.normalized_item_id == NormalizedItem.id
                )
            )
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
