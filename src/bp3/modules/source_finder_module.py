import time
from urllib.parse import urlparse

from tavily import TavilyClient

from core.config import settings
from src.bp3.models_llm import BaseModule, ProjectContext

client = TavilyClient(api_key=settings.tavily_api_key)


class SourceFinderModule(BaseModule):
    """Ищет новые домены-источники по КАЖДОМУ конкуренту через Tavily.

    Не зависит от текущей пачки новостей (`ctx.news`) — перебирает всех
    конкурентов из справочника (`ctx.competitors`), независимо от того,
    сколько новостей обработано в этом прогоне. Найденные домены попадают
    в `ctx.domains_to_add` (`{competitor_id: {'sources': [...]}}`) —
    дальше `SaveResultsModule` кладёт их в `source_candidate` (BP-7).
    """

    def process(self, ctx: ProjectContext) -> ProjectContext:
        """На каждого конкурента — один поиск Tavily, исключая уже
        известные домены (`ctx.domains`); сбой по одному конкуренту не
        прерывает остальных."""
        exclude_domains = ctx.domains or []
        companies = ctx.competitors or []

        company_data = {}

        for comp in companies:
            company_id, name = next(iter(comp.items()))
            try:
                company_id = int(company_id)
                name = str(name)

                response = client.search(
                    query=f'Найди новые источники новостей о компании {name}',
                    topic='news',
                    max_results=settings.bp3_search_max_results,
                    search_depth=settings.bp3_search_depth.value,
                    time_range=settings.bp3_search_time_range,
                    exclude_domains=exclude_domains,
                    include_answer=False,
                    include_raw_content=False,
                )
                results = response.get('results', [])
                sources = []
                for item in results:
                    url = item['url']
                    score = item.get('score')

                    parsed = urlparse(url)
                    host = parsed.netloc.lower()
                    if host.startswith('www.'):
                        host = host[4:]
                    sources.append(
                        {
                            'url': url,
                            'score': score,
                            'domain': host,
                        }
                    )

                company_data[company_id] = {
                    'sources': sources,
                }

            except Exception as e:
                print(f'Ошибка при поиске для {name} (ID={company_id}): {e}')
                company_data[company_id] = {'sources': []}

            time.sleep(1)

        ctx.domains_to_add = company_data
        return ctx
