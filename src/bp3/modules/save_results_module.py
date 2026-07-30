import os
from datetime import timedelta

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp3.models_llm import BaseModule, ProjectContext

load_dotenv()
DATABASE_URL = (
    f'postgresql://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}'
    f'@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}'
)
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class SaveResultsModule(BaseModule):
    """
    Сохраняет результаты категоризации, приоритетов, тональности,
    комментариев, действий и сроков в таблицу CategorizedEvent.
    """

    def process(self, ctx: ProjectContext) -> ProjectContext:
        # 1. Собираем все поля из ctx по id новости
        data_by_id = {}
        for item in ctx.category_news or []:
            data_by_id.setdefault(item['id'], {})['category_name'] = item.get(
                'category'
            )
        for item in ctx.priority or []:
            data_by_id.setdefault(item['id'], {})['priority'] = item.get(
                'priority'
            )
        for item in ctx.department or []:
            data_by_id.setdefault(item['id'], {})['department_name'] = item.get(
                'department'
            )
        for item in ctx.tone_of_news or []:
            data_by_id.setdefault(item['id'], {})['tonality'] = item.get(
                'tone_of_news'
            )
        for item in ctx.comments or []:
            data_by_id.setdefault(item['id'], {})['comment'] = item.get(
                'comments'
            )
        for item in ctx.actions or []:
            data_by_id.setdefault(item['id'], {})['action'] = item.get(
                'actions'
            )

        if not data_by_id:
            return ctx

        # 2. Собираем все id новостей, которые есть в ctx.category_news
        news_ids = set()
        for item in ctx.category_news or []:
            news_ids.add(item['id'])

        # 3. Загружаем справочники категорий и отделов
        with Session() as session:
            # Получаем даты новостей
            stmt_date = select(
                NormalizedItem.id, NormalizedItem.created_at
            ).where(NormalizedItem.id.in_(news_ids))
            rows_date = session.execute(stmt_date).mappings().all()
            news_date_map = {row['id']: row['created_at'] for row in rows_date}

            # Получаем все категории и id
            stmt_cat = select(Category.id, Category.name)
            rows_cat = session.execute(stmt_cat).mappings().all()
            cat_name_to_id = {
                row['name'].strip().lower(): row['id'] for row in rows_cat
            }

            # Получаем все отделы и id
            stmt_dep = select(Department.id, Department.name)
            rows_dep = session.execute(stmt_dep).mappings().all()
            dep_name_to_id = {
                row['name'].strip().lower(): row['id'] for row in rows_dep
            }

            # 4. Формируем и добавляем события
            for news_id, fields in data_by_id.items():
                # Преобразуем название категории в ID
                cat_name = fields.get('category_name')
                category_id = (
                    cat_name_to_id.get(cat_name.strip().lower())
                    if cat_name
                    else None
                )

                # Преобразуем название отдела в ID
                dep_name = fields.get('department_name')
                department_id = (
                    dep_name_to_id.get(dep_name.strip().lower())
                    if dep_name
                    else None
                )

                # Вычисляем deadline на основе приоритета и даты новости
                priority = fields.get('priority')
                news_date = news_date_map.get(news_id)
                deadline = None
                if news_date and priority:
                    if priority == 'П1':
                        deadline = news_date + timedelta(days=2)
                    elif priority == 'П2':
                        deadline = news_date + timedelta(days=7)

                # Создаём событие (deadline = None)
                event = CategorizedEvent(
                    normalized_item_id=news_id,
                    priority=fields.get('priority'),
                    category_id=category_id,
                    tonality=fields.get('tonality'),
                    action=fields.get('action'),
                    deadline=deadline,
                    department_id=department_id,
                    comment=fields.get('comment'),
                )
                session.add(event)

            session.commit()

        return ctx
