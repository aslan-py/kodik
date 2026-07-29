"""Этап BP-3: разметка событий (categorized_event) — СМЫСЛЫ.

Кладёт готовый gold-слой вместо вызова LLM. Нужен, чтобы работать с витриной
и алертами, не дожидаясь настоящей категоризации (её делает команда DS,
и гонять модель ради тестовых данных незачем).

Запуск:
    python -m core.scripts.stages.bp3

Разметка задаётся вручную по url события (MARKUP). Для события, которого нет
в MARKUP, берётся DEFAULT_MARKUP — так набор переживает добавление новых
фактов в stages/bp2 без правки этого файла.

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
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent, Category, Department

LLM_MODEL = 'gpt-4o-mini'
PROMPT_VERSION = 'v1.0'

# ============================================================================
#  Разметка: url события → смыслы
# ============================================================================

MARKUP: dict[str, dict] = {
    'https://big-news.ru/kaluga/12045': {
        'priority': PriorityLevel.p1,
        'category': 'надзорная санкция и юридический риск',
        'tonality': TonalityLevel.negative,
        'department': 'Юристы',
        'action': 'Подготовить юридическую позицию и оценить риски',
        'comment': 'Надзорный риск: представление прокуратуры',
    },
    'https://www.forbes.ru/biznes/456-den': {
        'priority': PriorityLevel.p2,
        'category': 'PR-активность конкурента',
        'tonality': TonalityLevel.positive,
        'department': 'PR',
        'action': 'Подготовить ответный PR-кейс',
        'comment': 'Активная промо-акция конкурента',
    },
    'https://argumenti.ru/irkutsk/2026/06/35let': {
        'priority': PriorityLevel.p3,
        'category': 'PR-активность конкурента',
        'tonality': TonalityLevel.positive,
        'department': 'PR',
        'action': None,
        'comment': 'Юбилейная активность, к сведению',
    },
    'https://ugra-news.ru/surgut/reforma': {
        'priority': PriorityLevel.p2,
        'category': 'системная проблема (возможность для входа)',
        'tonality': TonalityLevel.negative,
        'department': 'Аналитика',
        'action': 'Оценить возможность входа на рынок Сургута',
        'comment': 'Системная проблема у конкурента — окно возможностей',
    },
    'https://www.kzn.ru/meta/news/600': {
        'priority': PriorityLevel.p3,
        'category': 'косвенное упоминание',
        'tonality': TonalityLevel.neutral,
        'department': 'Аналитика',
        'action': None,
        'comment': 'Косвенное упоминание, фоновая активность',
    },
    'https://spb.bezformata.com/stolovye': {
        'priority': PriorityLevel.p3,
        'category': 'признание качества и конкурсы',
        'tonality': TonalityLevel.positive,
        'department': 'Маркетинг',
        'action': None,
        'comment': 'Признание качества конкурента',
    },
    'https://samadm.ru/news/rekonstrukciya': {
        'priority': PriorityLevel.p3,
        'category': 'PR-активность конкурента',
        'tonality': TonalityLevel.neutral,
        'department': 'PR',
        'action': None,
        'comment': 'Инфраструктурная активность',
    },
    'https://samara450.ru/dolg': {
        'priority': PriorityLevel.p2,
        'category': 'репутационный риск',
        'tonality': TonalityLevel.negative,
        'department': 'PR',
        'action': 'Мониторить репутационный фон конкурента',
        'comment': 'Рост задолженности — репутационный риск',
    },
    'https://news.rambler.ru/incident/54321': {
        'priority': PriorityLevel.p1,
        'category': 'надзорная санкция и юридический риск',
        'tonality': TonalityLevel.negative,
        'department': 'Юристы',
        'action': 'Отследить ход судебного разбирательства',
        'comment': 'Судебный процесс вокруг конкурента',
    },
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
