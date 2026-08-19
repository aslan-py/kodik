import json
from pathlib import Path

from src.bp3.models_llm import LLMModule, ProjectContext, ToneResponse

PROMPT_PATH = Path(__file__).parent.parent / 'prompts' / 'tone_prompt.txt'

NOISE_CATEGORY = 'информационный шум'


class ToneAnalysisModule(LLMModule):
    def __init__(self, llm):
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(ToneResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
        """Для новостей категории «информационный шум» —
        `tone_of_news='irrelevant'` без обращения к LLM;
        для остальных — один вызов LLM на всю пачку."""
        news = ctx.news or []
        if not news:
            ctx.tone_of_news = []
            return ctx

        category_by_id = {
            item.get('id'): (item.get('category') or '').strip().lower()
            for item in (ctx.category_news or [])
        }

        valid_news = []
        noise_ids = set()
        for item in news:
            news_id = item.get('id')
            if category_by_id.get(news_id) == NOISE_CATEGORY:
                noise_ids.add(news_id)
            else:
                valid_news.append(item)

        if not valid_news:
            ctx.tone_of_news = [
                {'id': item.get('id'), 'tone_of_news': 'irrelevant'}
                for item in news
            ]
            return ctx

        with open(PROMPT_PATH, encoding='utf-8') as f:
            template = f.read()

        prompt = template.format(
            news_json=json.dumps(valid_news, ensure_ascii=False),
            len_news=len(valid_news),
        )

        try:
            response: ToneResponse = self.invoke_llm(prompt, ctx)
            tone_map = {item.id: item.tone_of_news for item in response.items}
        except Exception as e:
            print(f'[ОШИБКА] ToneAnalysisModule: {e}')
            tone_map = {item.get('id'): None for item in valid_news}

        tone_of_news = []
        for item in news:
            news_id = item.get('id')
            if news_id in noise_ids:
                tone_of_news.append(
                    {'id': news_id, 'tone_of_news': 'irrelevant'}
                )
            else:
                tone_of_news.append(
                    {'id': news_id, 'tone_of_news': tone_map.get(news_id)}
                )
        ctx.tone_of_news = tone_of_news
        return ctx
