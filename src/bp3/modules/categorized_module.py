"""Определение категории новости."""

import json
from pathlib import Path

from src.bp3.models_llm import CategorizedResponse, LLMModule, ProjectContext

PROMPT_PATH = Path(__file__).parent.parent / 'prompts' / 'categorize_prompt.txt'


class CategorizedModule(LLMModule):
    """Определяет категорию каждой новости из списка категорий в БД."""

    def __init__(self, llm):
        """Настраивает формат ответа LLM."""
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(CategorizedResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
        """Отправляет новости в LLM и сохраняет полученные категории."""
        news = ctx.news or []
        if not news:
            ctx.category_news = []
            return ctx

        with open(PROMPT_PATH, encoding='utf-8') as f:
            template = f.read()

        prompt = template.format(
            news_json=json.dumps(news, ensure_ascii=False),
            cat_json=json.dumps(ctx.manual_cat or [], ensure_ascii=False),
            len_news=len(news),
        )

        try:
            response: CategorizedResponse = self.invoke_llm(prompt, ctx)
            categories_by_id = {
                item.id: item.category for item in response.items
            }
            ctx.category_news = [
                {
                    'id': item['id'],
                    'text': item.get('text'),
                    'category': categories_by_id.get(item['id']),
                }
                for item in news
            ]
        except Exception as e:
            print(f'[ОШИБКА] CategorizedModule: {e}')
            ctx.category_news = [
                {
                    'id': item.get('id'),
                    'text': item.get('text'),
                    'category': None,
                }
                for item in news
            ]
        return ctx
