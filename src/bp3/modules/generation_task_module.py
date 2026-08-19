"""Формирование задач по рекомендации."""

import json
from pathlib import Path

from src.bp3.models_llm import GenerationTaskResponse, LLMModule, ProjectContext

PROMPT_PATH = (
    Path(__file__).parent.parent / 'prompts' / 'generation_task_prompt.txt'
)


class GenerationTaskModule(LLMModule):
    """Формирует от 1 до 3 задач по рекомендации для каждой новости."""

    def __init__(self, llm):
        """Настраивает формат ответа LLM."""
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(GenerationTaskResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
        """LLM формирует задачи из рекомендаций по каждой новости.

        Новости без рекомендации пропускаются — задачи для них не
        формируются.
        """
        actions = ctx.actions or []
        if not actions:
            ctx.tasks = []
            return ctx

        # Разделяем действия на «валидные» и «невалидные» (action == None)
        valid_actions = []
        invalid_ids = set()
        for item in actions:
            action_val = item.get('actions')
            # Считаем невалидным, если action равен None
            if action_val is None:
                invalid_ids.add(item.get('id'))
            else:
                valid_actions.append(item)

        # Если нет ни одного валидного действия — все задачи будут None
        if not valid_actions:
            ctx.tasks = [
                {'id': item.get('id'), 'tasks': None} for item in actions
            ]
            return ctx

        # Подготовка данных для LLM (только валидные действия)
        actions_for_prompt = [
            {'id': item.get('id'), 'action': item.get('actions')}
            for item in valid_actions
        ]

        with open(PROMPT_PATH, encoding='utf-8') as f:
            template = f.read()

        prompt = template.format(
            actions_json=json.dumps(
                actions_for_prompt, ensure_ascii=False, indent=2
            ),
            len_actions=len(actions_for_prompt),
        )

        try:
            response: GenerationTaskResponse = self.invoke_llm(prompt, ctx)
            # Сопоставляем id -> список задач из ответа LLM
            generated_tasks_map = {
                item.id: item.tasks for item in response.items
            }
        except Exception as e:
            print(f'[ОШИБКА] GenerationTaskModule: {e}')
            generated_tasks_map = {
                item.get('id'): ['Ошибка генерации задач']
                for item in valid_actions
            }

        # Формируем итоговый список для всех исходных actions
        result_tasks = []
        for item in actions:
            news_id = item.get('id')
            if news_id in generated_tasks_map:
                result_tasks.append(
                    {'id': news_id, 'tasks': generated_tasks_map[news_id]}
                )
            else:
                result_tasks.append({'id': news_id, 'tasks': None})

        ctx.tasks = result_tasks
        return ctx
