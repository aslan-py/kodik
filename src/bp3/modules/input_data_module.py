from src.bp3.fetch_data import fetch_data
from src.bp3.models_llm import BaseModule, ProjectContext


class InputDataModule(BaseModule):
    def process(self, ctx: ProjectContext) -> ProjectContext:
        try:
            news_list, cat_list, depart_list = fetch_data()
        except Exception as e:
            raise RuntimeError(f'Ошибка загрузки данных из БД: {e}') from e

        ctx.news = news_list
        ctx.manual_cat = cat_list
        ctx.manual_dept = depart_list
        return ctx
