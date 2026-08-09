from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.config import settings
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp3.models_llm import BaseModule, ProjectContext

DATABASE_URL = (
    f'postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}'
    f'@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}'
)
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class SaveResultsModule(BaseModule):
    """
    Сохраняет результаты категоризации, приоритетов, тональности,
    комментариев, действий, сроков, медиа-индекса и найденных источников
    в соответствующие таблицы.
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
        for item in ctx.tasks or []:
            data_by_id.setdefault(item['id'], {})['task'] = item.get('tasks')
        for item in ctx.expected_result or []:
            data_by_id.setdefault(item['id'], {})['expected_result'] = item.get(
                'expected_result'
            )

        if not data_by_id:
            return ctx

        news_ids = set(data_by_id.keys())

        # 2. Индекс медиа-активности по competitor_id
        index_by_competitor = {}
        if ctx.media_activity_index:
            index_by_competitor = {
                item['competitor_id']: item['media_activity_index']
                for item in ctx.media_activity_index
            }

        with Session() as session:
            # Получаем даты новостей и идентификаторы конкурентов
            stmt_date = select(
                NormalizedItem.id,
                NormalizedItem.created_at,
                NormalizedItem.competitor_id,
            ).where(NormalizedItem.id.in_(news_ids))
            rows_info = session.execute(stmt_date).mappings().all()
            news_info_map = {
                row['id']: {
                    'created_at': row['created_at'],
                    'competitor_id': row['competitor_id'],
                }
                for row in rows_info
            }

            # Справочник категорий
            stmt_cat = select(Category.id, Category.name)
            rows_cat = session.execute(stmt_cat).mappings().all()
            cat_name_to_id = {
                row['name'].strip().lower(): row['id'] for row in rows_cat
            }

            # Справочник отделов
            stmt_dep = select(Department.id, Department.name)
            rows_dep = session.execute(stmt_dep).mappings().all()
            dep_name_to_id = {
                row['name'].strip().lower(): row['id'] for row in rows_dep
            }

            # 3. Сохраняем категоризированные события
            for news_id, fields in data_by_id.items():
                news_info = news_info_map.get(news_id)
                if not news_info:
                    continue

                cat_name = fields.get('category_name')
                category_id = (
                    cat_name_to_id.get(cat_name.strip().lower())
                    if cat_name
                    else None
                )

                dep_name = fields.get('department_name')
                department_id = (
                    dep_name_to_id.get(dep_name.strip().lower())
                    if dep_name
                    else None
                )

                priority = fields.get('priority')
                news_date = news_info['created_at']
                deadline = None
                if news_date and priority:
                    if priority == 'p1':
                        deadline = news_date + timedelta(days=2)
                    elif priority == 'p2':
                        deadline = news_date + timedelta(days=7)

                competitor_id = news_info['competitor_id']
                media_index = index_by_competitor.get(competitor_id)

                event = CategorizedEvent(
                    normalized_item_id=news_id,
                    priority=priority,
                    category_id=category_id,
                    tonality=fields.get('tonality'),
                    action=fields.get('action'),
                    task=fields.get('task'),
                    expected_result=fields.get('expected_result'),
                    deadline=deadline,
                    department_id=department_id,
                    comment=fields.get('comment'),
                    media_index=media_index,
                )
                session.add(event)

            #            # 4. Сохраняем найденные источники
            #            domains_to_add = ctx.domains_to_add or {}
            #            for competitor_id, data in domains_to_add.items():
            #                for src in data.get('sources', []):
            #                    url = src.get('url')
            #                    score = src.get('score')
            #                    domain = src.get('domain')
            #                    if not url or not domain:
            #                        continue
            #
            #                    source_candidate = SourceCandidate(
            #                        competitor_id=competitor_id,
            #                        url=url,
            #                        score=score,
            #                        domain= domain,
            #                    )
            #                    session.add(source_candidate)

            session.commit()

        return ctx
