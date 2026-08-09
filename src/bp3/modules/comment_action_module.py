import json
from pathlib import Path

from src.bp3.models_llm import CommentActionResponse, LLMModule, ProjectContext
from src.bp3.utils import clear_p4_comments_actions

PROMPT_PATH = (
    Path(__file__).parent.parent / 'prompts' / 'comment_action_prompt.txt'
)


class CommentActionModule(LLMModule):
    def __init__(self, llm):
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(CommentActionResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
        categorized_news = ctx.category_news or []
        if not categorized_news:
            ctx.comments = []
            ctx.actions = []
            return ctx

        priority_dict = {
            item['id']: item.get('priority') for item in (ctx.priority or [])
        }
        deadline_dict = {
            item['id']: item.get('deadline') for item in (ctx.deadline or [])
        }
        department_dict = {
            item['id']: item.get('department')
            for item in (ctx.department or [])
        }
        tone_dict = {
            item['id']: item.get('tone_of_news')
            for item in (ctx.tone_of_news or [])
        }

        enriched_news = []
        for item in categorized_news:
            news_id = item.get('id')
            enriched_news.append(
                {
                    'id': news_id,
                    'text': item.get('text') or 'Текст отсутствует',
                    'category': item.get('category') or 'Неизвестная категория',
                    'priority': priority_dict.get(news_id, 'Не назначен'),
                    'deadline': deadline_dict.get(news_id, 'Не указан'),
                    'department': department_dict.get(news_id, 'Не назначен'),
                    'tone': tone_dict.get(news_id, 'Не определена'),
                }
            )

        with open(PROMPT_PATH, encoding='utf-8') as f:
            template = f.read()

        prompt = template.format(
            enriched_news_json=json.dumps(
                enriched_news, ensure_ascii=False, indent=2
            ),
            len_news=len(enriched_news),
        )

        try:
            response: CommentActionResponse = self.structured_llm.invoke(prompt)
            ctx.comments = [
                {'id': item.id, 'comments': item.comments}
                for item in response.items
            ]
            ctx.actions = [
                {'id': item.id, 'actions': item.actions}
                for item in response.items
            ]
        except Exception as e:
            print(f'[ОШИБКА] CommentActionModule: {e}')
            ctx.comments = [
                {'id': item.get('id'), 'comments': 'Ошибка генерации'}
                for item in categorized_news
            ]
            ctx.actions = [
                {'id': item.get('id'), 'actions': 'Требуется ручной анализ'}
                for item in categorized_news
            ]
            pass

        clear_p4_comments_actions(ctx.comments, ctx.actions, priority_dict)

        return ctx
