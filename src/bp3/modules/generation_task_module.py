import json
from pathlib import Path

from src.bp3.models_llm import GenerationTaskResponse, LLMModule, ProjectContext

PROMPT_PATH = (
    Path(__file__).parent.parent / 'prompts' / 'generation_task_prompt.txt'
)


class GenerationTaskModule(LLMModule):
    def __init__(self, llm):
        super().__init__(llm)
        self.structured_llm = llm.with_structured_output(GenerationTaskResponse)

    def process(self, ctx: ProjectContext) -> ProjectContext:
        actions = ctx.actions or []
        if not actions:
            ctx.tasks = []
            return ctx

        actions_for_prompt = []
        for item in actions:
            actions_for_prompt.append(
                {
                    'id': item.get('id'),
                    'action': item.get('actions', 'Нет рекомендации'),
                }
            )

        with open(PROMPT_PATH, encoding='utf-8') as f:
            template = f.read()

        prompt = template.format(
            actions_json=json.dumps(
                actions_for_prompt, ensure_ascii=False, indent=2
            ),
            len_actions=len(actions_for_prompt),
        )

        try:
            response: GenerationTaskResponse = self.structured_llm.invoke(
                prompt
            )
            ctx.tasks = [
                {'id': item.id, 'tasks': item.tasks} for item in response.items
            ]
        except Exception as e:
            print(f'[ОШИБКА] GenerationTaskModule: {e}')
            ctx.tasks = [
                {'id': item.get('id'), 'tasks': ['Ошибка генерации задач']}
                for item in actions
            ]
        return ctx
