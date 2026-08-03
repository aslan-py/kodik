from src.bp3.fetch_data import fetch_data, fetch_news_stats
from src.bp3.models_llm import BaseModule, ProjectContext


class InputDataModule(BaseModule):
    def process(self, ctx: ProjectContext) -> ProjectContext:
        try:
            news_list, cat_list, depart_list = fetch_data()
            news_stats, count_sources = fetch_news_stats()
        except Exception as e:
            raise RuntimeError(f'Ошибка загрузки данных из БД: {e}') from e

        ctx.news = news_list
        ctx.manual_cat = cat_list
        ctx.manual_dept = depart_list
        ctx.news_stats = news_stats
        ctx.count_sources = count_sources
        return ctx
