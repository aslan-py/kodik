import json
from pathlib import Path

from src.bp3.models_llm import CategorizedResponse, LLMModule, ProjectContext

PROMPT_PATH = Path(__file__).parent.parent / 'prompts' / 'categorize_prompt.txt'


class CategorizedModule(LLMModule):
    def __init__(self, llm):
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(CategorizedResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
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
            response: CategorizedResponse = self.structured_llm.invoke(prompt)
            ctx.category_news = [item.model_dump() for item in response.items]
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
