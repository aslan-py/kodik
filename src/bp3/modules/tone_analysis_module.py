import json
from pathlib import Path

from src.bp3.models_llm import LLMModule, ProjectContext, ToneResponse

PROMPT_PATH = Path(__file__).parent.parent / 'prompts' / 'tone_prompt.txt'


class ToneAnalysisModule(LLMModule):
    def __init__(self, llm):
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(ToneResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
        news = ctx.news or []
        if not news:
            ctx.tone_of_news = []
            return ctx

        with open(PROMPT_PATH, encoding='utf-8') as f:
            template = f.read()

        prompt = template.format(
            news_json=json.dumps(news, ensure_ascii=False), len_news=len(news)
        )

        try:
            response: ToneResponse = self.structured_llm.invoke(prompt)
            ctx.tone_of_news = [item.model_dump() for item in response.items]
        except Exception as e:
            print(f'[ОШИБКА] ToneAnalysisModule: {e}')
            ctx.tone_of_news = [
                {'id': item.get('id'), 'tone_of_news': None} for item in news
            ]
        return ctx
