from core.enums import PriorityLevel
from src.bp3.models_llm import BaseModule, ProjectContext

ACTION_RULES = {
    'надзорная санкция и юридический риск': (
        PriorityLevel.p1,
        'срок 48 часов',
        'Юристы',
    ),
    'репутационный риск': (PriorityLevel.p1, 'срок 48 часов', 'PR'),
    'pr-активность конкурента': (PriorityLevel.p2, 'срок 1 неделя', 'PR'),
    'системная проблема (возможность для входа)': (
        PriorityLevel.p2,
        'срок 1 неделя',
        'Аналитика',
    ),
    'признание качества и конкурсы': (
        PriorityLevel.p3,
        'отслеживать',
        'Маркетинг',
    ),
    'косвенное упоминание': (PriorityLevel.p3, 'отслеживать', 'Аналитика'),
    'информационный шум': (PriorityLevel.p4, 'игнорировать', None),
}
UNKNOWN_CATEGORY_RULE = (
    PriorityLevel.p2,
    'категорию добавить в базу',
    'Аналитика',
)


class ActionPlanningModule(BaseModule):
    def process(self, ctx: ProjectContext) -> ProjectContext:
        categorized_news = ctx.category_news or []

        priority_list = []
        deadline_list = []
        department_list = []

        for item in categorized_news:
            news_id = item.get('id')
            category = item.get('category')

            if category is None:
                priority, deadline, department = UNKNOWN_CATEGORY_RULE
            else:
                priority, deadline, department = ACTION_RULES.get(
                    category.strip().lower(),
                    UNKNOWN_CATEGORY_RULE,
                )

            priority_list.append({'id': news_id, 'priority': priority})
            deadline_list.append({'id': news_id, 'deadline': deadline})
            department_list.append({'id': news_id, 'department': department})

        ctx.priority = priority_list
        ctx.deadline = deadline_list
        ctx.department = department_list
        return ctx
