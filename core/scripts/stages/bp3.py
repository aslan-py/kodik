"""Этап BP-3: разметка событий (categorized_event) — СМЫСЛЫ.

Кладёт готовый gold-слой вместо вызова LLM. Нужен, чтобы работать с витриной
и алертами, не дожидаясь настоящей категоризации (её делает команда DS,
и гонять модель ради тестовых данных незачем).

Запуск:
    python -m core.scripts.stages.bp3

Разметка лежит в демо-наборе новостей (stages/news_data.py) — колонки
category / priority / tonality / department / action / comment того же CSV,
из которого BP-1 и BP-2 берут контент; событие находится по url. Для
события, которого в наборе нет, берётся DEFAULT_MARKUP — так набор
переживает появление новых фактов без правки этого файла.

Что здесь имитирует LLM, а что делает код (как и в бою):
  - LLM: приоритет, категория, тональность, действие, комментарий, отдел;
  - код: deadline (П1 = дата + 2 дня, П2 = +7 дней) — арифметику дат модели
    не доверяют; llm_model и prompt_version — метаданные прогона.

Размечаются ТОЛЬКО события со status=ok: отсеянное разметку не получает.
Требует залитых фактов (stages/bp2 либо настоящий прогон run_bp2).
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import NormStatus, PriorityLevel, TonalityLevel
from core.scripts.stages.cascade import clear_from
from core.scripts.stages.news_data import NEWS
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department

LLM_MODEL = 'gpt-4o-mini'
PROMPT_VERSION = 'v1.0'

# ============================================================================
#  Разметка: url события → смыслы (из CSV, только у чистых событий)
# ============================================================================

MARKUP: dict[str, dict] = {
    news.url: {
        'priority': news.priority,
        'category': news.category,
        'tonality': news.tonality,
        'department': news.department,
        'action': news.action,
        'comment': news.comment,
    }
    for news in NEWS
    if news.is_clean
}

DEFAULT_MARKUP = {
    'priority': PriorityLevel.p3,
    'category': 'косвенное упоминание',
    'tonality': TonalityLevel.neutral,
    'department': 'Аналитика',
    'action': None,
    'comment': 'Фоновая активность (дефолтная разметка)',
}


def compute_deadline(priority: PriorityLevel, published: date | None):
    """Срок реакции считает КОД, а не LLM (ТЗ: П1 = +2 дня, П2 = +7 дней)."""
    if published is None:
        return None
    if priority == PriorityLevel.p1:
        return published + timedelta(days=2)
    if priority == PriorityLevel.p2:
        return published + timedelta(days=7)
    return None


# ============================================================================
#  Этап
# ============================================================================


async def seed(session: AsyncSession) -> int:
    """Разметить все чистые события (одна разметка на событие, 1:1)."""
    categories = {
        c.name: c.id
        for c in (await session.execute(select(Category))).scalars()
    }
    departments = {
        d.name: d.id
        for d in (await session.execute(select(Department))).scalars()
    }
    items = (
        await session.execute(
            select(NormalizedItem).where(NormalizedItem.status == NormStatus.ok)
        )
    ).scalars()

    added = 0
    for item in items:
        markup = MARKUP.get(item.url, DEFAULT_MARKUP)
        session.add(
            CategorizedEvent(
                normalized_item_id=item.id,
                priority=markup['priority'],
                category_id=categories[markup['category']],
                tonality=markup['tonality'],
                media_index=None,  # приходит из агрегатора, не от LLM
                action=markup['action'],
                deadline=compute_deadline(
                    markup['priority'], item.published_at
                ),
                department_id=departments[markup['department']],
                comment=markup['comment'],
                llm_model=LLM_MODEL,
                prompt_version=PROMPT_VERSION,
            )
        )
        added += 1

    await session.flush()
    if not added:
        raise RuntimeError(
            'Нет чистых событий для разметки. '
            'Сначала: python -m core.scripts.stages.bp2'
        )
    return added


async def clear(session: AsyncSession) -> int:
    """Снести разметку и всё, что на ней построено (витрину, алерты)."""
    return await clear_from(session, CategorizedEvent)


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-3 (categorized_event)', clear, seed)
