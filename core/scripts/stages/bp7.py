"""Этап BP-7 (заглушка): наполнение очереди кандидатов `source_candidate`.

Агент, который сам ищет кандидатов в интернете и оценивает их через LLM, —
следующая итерация (см. src/bp7/BP7_README.md, «Осознанно не реализовано»).
Пока такого агента нет, здесь — несколько демо-строк по образцу
stages/bp1.py и stages/bp6.py: часть кандидатов со `score` выше текущего
порога (SOURCE_CANDIDATE_SCORE_THRESHOLD), часть ниже — чтобы перенос
(src/bp7/pipeline.py::run_bp7_promotion) было на чём проверить.

Запуск:
    python -m core.scripts.stages.bp7

Требует залитых справочников (нужен хотя бы один Competitor).
"""

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from src.bp1.models import Competitor
from src.bp7.models import SourceCandidate

# Демо-домены: (домен, url, смещение score относительно порога).
# Положительное смещение — кандидат должен пройти перенос, отрицательное —
# остаться в очереди (score ниже порога).
CANDIDATES: list[tuple[str, str, Decimal]] = [
    ('newsdata-example.ru', 'https://newsdata-example.ru/', Decimal('0.30')),
    ('marketwatch-demo.ru', 'https://marketwatch-demo.ru/', Decimal('0.20')),
    (
        'industry-digest-demo.ru',
        'https://industry-digest-demo.ru/',
        Decimal('0.10'),
    ),
    ('low-signal-demo.ru', 'https://low-signal-demo.ru/', Decimal('-0.10')),
    (
        'spam-aggregator-demo.ru',
        'https://spam-aggregator-demo.ru/',
        Decimal('-0.20'),
    ),
    ('irrelevant-demo.ru', 'https://irrelevant-demo.ru/', Decimal('-0.30')),
]


def _clamp(value: Decimal) -> Decimal:
    """Score живёт строго в [0.00, 1.00] (CHECK-констрейнт в БД)."""
    if value < 0:
        return Decimal('0.00')
    if value > 1:
        return Decimal('1.00')
    return value


async def seed(session: AsyncSession) -> int:
    """Залить демо-кандидатов вокруг текущего порога (`.env`).

    Порог берётся из конфига в момент запуска — не хардкодится, — чтобы
    заглушка оставалась осмысленной при любом SOURCE_CANDIDATE_SCORE_THRESHOLD.
    """
    threshold = Decimal(str(settings.source_candidate_score_threshold))

    competitors = (
        (await session.execute(select(Competitor).limit(len(CANDIDATES))))
        .scalars()
        .all()
    )
    if not competitors:
        raise RuntimeError(
            'Справочники не залиты — нет ни одного Competitor. '
            'Сначала: python -m core.scripts.stages.dictionaries'
        )

    added = 0
    for index, (domain, url, offset) in enumerate(CANDIDATES):
        competitor = competitors[index % len(competitors)]
        session.add(
            SourceCandidate(
                domain=domain,
                url=url,
                competitor_id=competitor.id,
                score=_clamp(threshold + offset),
            )
        )
        added += 1

    await session.flush()
    return added


async def clear(session: AsyncSession) -> int:
    """Снести кандидатов. Лист таблицы (не часть PIPELINE_ORDER) — просто
    delete, без clear_from (та работает только с цепочкой данных пайплайна).
    """
    result = await session.execute(delete(SourceCandidate))
    return result.rowcount


if __name__ == '__main__':
    from core.scripts.stages.cascade import run_stage

    run_stage('BP-7 (заглушка source_candidate)', clear, seed)
