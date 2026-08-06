from src.bp3.fetch_data import fetch_data, fetch_news_stats, fetch_seed_urls
from src.bp3.models_llm import BaseModule, ProjectContext
from src.bp3.utils import extract_domains


class InputDataModule(BaseModule):
    def process(self, ctx: ProjectContext) -> ProjectContext:
        try:
            news_list, cat_list, depart_list = fetch_data()
            news_stats, count_sources = fetch_news_stats()
            list_urls, unique_domains, compt_list = fetch_seed_urls()
        except Exception as e:
            raise RuntimeError(f'Ошибка загрузки данных из БД: {e}') from e

        domain_list = extract_domains(list_urls, unique_domains)

        ctx.news = news_list
        ctx.manual_cat = cat_list
        ctx.manual_dept = depart_list
        ctx.news_stats = news_stats
        ctx.count_sources = count_sources
        ctx.domains = domain_list
        ctx.competitors = compt_list
        return ctx
