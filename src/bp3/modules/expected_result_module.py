import json
from pathlib import Path

from src.bp3.models_llm import ExpectedResultResponse, LLMModule, ProjectContext

PROMPT_PATH = (
    Path(__file__).parent.parent / 'prompts' / 'expected_result_prompt.txt'
)


class ExpectedResultModule(LLMModule):
    """LLM-шаг: ожидаемый результат по событию (комментарий+действие+задачи).

    Заполняет `categorized_event.expected_result` (см. capability
    `bp3/categorized-event-expected-result`).
    """

    def __init__(self, llm):
        """Обернуть LLM в structured output по схеме `ExpectedResultResponse`."""  # noqa
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(ExpectedResultResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
        """Для новостей без задач (`tasks` пуст/None) — `expected_result=None`
        без обращения к LLM; для остальных — один вызов LLM на всю пачку."""
        # Берём все новости из category_news
        all_news = ctx.category_news or []
        if not all_news:
            ctx.expected_result = []
            return ctx

        # Словари для доступа к комментариям, действиям и задачам по id
        comments_dict = {
            item['id']: item.get('comments', '')
            for item in (ctx.comments or [])
        }
        actions_dict = {
            item['id']: item.get('actions', '') for item in (ctx.actions or [])
        }
        tasks_dict = {
            item['id']: item.get('tasks') for item in (ctx.tasks or [])
        }

        # Разделяем новости на те, что с задачами, и те, что без
        valid_news = []
        invalid_ids = set()

        for news in all_news:
            news_id = news.get('id')
            tasks = tasks_dict.get(news_id)
            if tasks is not None and tasks != []:
                valid_news.append(news)
            else:
                invalid_ids.add(news_id)

        if not valid_news:
            ctx.expected_result = [
                {'id': item['id'], 'expected_result': None} for item in all_news
            ]
            return ctx

        # Подготовка данных для LLM
        data_for_prompt = []
        for news in valid_news:
            news_id = news['id']
            data_for_prompt.append(
                {
                    'id': news_id,
                    'comment': comments_dict.get(news_id, ''),
                    'action': actions_dict.get(news_id, ''),
                    'tasks': tasks_dict.get(news_id, []),
                }
            )

        with open(PROMPT_PATH, encoding='utf-8') as f:
            template = f.read()

        prompt = template.format(
            data_json=json.dumps(data_for_prompt, ensure_ascii=False, indent=2),
            len_data=len(data_for_prompt),
        )

        try:
            response: ExpectedResultResponse = self.structured_llm.invoke(
                prompt
            )
            generated_map = {
                item.id: item.expected_result for item in response.items
            }
        except Exception as e:
            print(f'[ОШИБКА] ExpectedResultModule: {e}')
            generated_map = {
                news['id']: 'Ошибка формирования ожидаемого результата'
                for news in valid_news
            }

        # Формируем итоговый список для ВСЕХ новостей
        expected_result = []
        for news in all_news:
            news_id = news['id']
            if news_id in invalid_ids:
                expected_result.append({'id': news_id, 'expected_result': None})
            else:
                expected_result.append(
                    {
                        'id': news_id,
                        'expected_result': generated_map.get(
                            news_id, 'Ошибка генерации'
                        ),
                    }
                )

        ctx.expected_result = expected_result
        return ctx
