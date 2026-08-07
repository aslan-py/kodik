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

        company_data = {}

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

                # Извлечение доменов из источников
                domains = []
                for src in sources:
                    parsed = urlparse(src['url'])
                    host = parsed.netloc.lower()
                    if host.startswith('www.'):
                        host = host[4:]
                    domains.append(host)
                domains = list(set(domains))

                company_data[company_id] = {
                    'sources': sources,
                    'domains': domains,
                }

            except Exception as e:
                print(f'Ошибка при поиске для {name} (ID={company_id}): {e}')
                company_data[company_id] = {'sources': [], 'domains': []}

            time.sleep(1)

        ctx.domains_to_add = company_data
        return ctx
