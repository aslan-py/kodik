import os
import time
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient

from src.bp3.models_llm import BaseModule, ProjectContext

load_dotenv()

tavily_api_key = os.getenv('TAVILY_API_KEY')
if not tavily_api_key:
    raise ValueError('TAVILY_API_KEY не задан')

client = TavilyClient(api_key=tavily_api_key)


class SourceFinderModule(BaseModule):
    def process(self, ctx: ProjectContext) -> ProjectContext:
        exclude_domains = ctx.domains or []
        companies = ctx.competitors or []

        company_sources: dict[int, list[dict]] = {}
        all_urls = []

        for comp in companies:
            company_id, name = next(iter(comp.items()))
            try:
                company_id = int(company_id)
                name = str(name)

                response = client.search(
                    query=f'Найди новые источники новостей о компании {name}',
                    topic='news',
                    max_results=10,
                    search_depth='basic',
                    time_range='week',
                    exclude_domains=exclude_domains,
                    include_answer=False,
                    include_raw_content=False,
                )
                results = response.get('results', [])
                sources = [
                    {'url': item['url'], 'score': item.get('score')}
                    for item in results
                ]
                company_sources[company_id] = sources

                for src in sources:
                    all_urls.append(src['url'])

            except Exception as e:
                print(f'Ошибка при поиске для {name} (ID={company_id}): {e}')
                company_sources[company_id] = []

            time.sleep(1)

        ctx.company_sources = company_sources
        #        if all_urls:
        #            ctx.urls = list(set(all_urls))
        domains = []
        for url in all_urls:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            if host.startswith('www.'):
                host = host[4:]
            domains.append(host)

        domains_to_add = list(set(domains))
        ctx.domains_to_add = domains_to_add

        return ctx
