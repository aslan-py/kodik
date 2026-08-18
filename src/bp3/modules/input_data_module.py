import asyncio

from src.bp3.fetch_data import fetch_data, fetch_news_stats, fetch_seed_urls
from src.bp3.models_llm import BaseModule, ProjectContext
from src.bp3.utils import extract_domains


class InputDataModule(BaseModule):
    """Загружает из БД новости под категоризацию и справочники LLM-промптов.

    `fetch_data`/`fetch_news_stats`/`fetch_seed_urls` — `async def`
    (AsyncSessionLocal), а `process()` синхронный (контракт BaseModule) —
    мост через общий event loop потока (`asyncio.get_event_loop()`), НЕ
    через `asyncio.run()` на каждый вызов: несколько отдельных
    `asyncio.run()` в одном потоке рвут пул соединений `core.database.engine`
    на Windows (см. докстринг `src/bp3/pipeline.py`). Loop создаётся один
    раз на весь прогон в `_run_pipeline_in_thread` (`src/bp3/pipeline.py`).
    """

    def process(self, ctx: ProjectContext) -> ProjectContext:
        loop = asyncio.get_event_loop()
        try:
            news_list, cat_list, depart_list = loop.run_until_complete(
                fetch_data()
            )
            news_stats, count_sources = loop.run_until_complete(
                fetch_news_stats()
            )
            list_urls, unique_domains, compt_list = loop.run_until_complete(
                fetch_seed_urls()
            )
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
