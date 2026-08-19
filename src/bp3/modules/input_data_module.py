"""Загрузка исходных данных из базы."""

import asyncio

from src.bp3.fetch_data import fetch_data, fetch_news_stats, fetch_seed_urls
from src.bp3.models_llm import BaseModule, ProjectContext
from src.bp3.utils import extract_domains


class InputDataModule(BaseModule):
    """Загружает из базы новости и справочники для работы остальных модулей.

    Запросы к базе асинхронные, а модуль синхронный, поэтому они
    выполняются в общем event loop потока. Свой event loop здесь
    создавать нельзя — это рвёт пул соединений с базой (подробности в
    `src/bp3/pipeline.py`).
    """

    def process(self, ctx: ProjectContext) -> ProjectContext:
        """Загружает новости, справочники, статистику и список доменов."""
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
