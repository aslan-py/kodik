"""Реестр этапов конвейера: `{номер -> дескриптор}`.

Единственный источник правды о том, какая функция стоит за каким этапом.
Ничего не реализует сам — только ссылается на уже существующие функции:
`src/bpN/pipeline.py` (реальные этапы) и `core/scripts/stages/*.py`
(заглушки). Заменить заглушку на финальную реализацию, когда она появится, —
значит поменять одну ссылку здесь, форма реестра не меняется.

CLI (core/pipeline/cli.py) — сегодня единственный потребитель. API и
FastAdmin — следующие итерации (см. proposal.md, Non-goals), реестр
рассчитан дёргаться и оттуда без переписывания.
"""

import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.scripts.stages import bp1_stub
from src.bp1.models import RawItem
from src.bp2.models import NormalizedItem
from src.bp2.pipeline import run_bp2
from src.bp3.models import CategorizedEvent
from src.bp3.pipeline import run_bp3
from src.bp4.models import ShowcaseEvent
from src.bp4.pipeline import run_bp4
from src.bp5.pipeline import run_bp5
from src.bp6.pipeline import run_bp6
from src.bp7.pipeline import run_bp7_promotion


@dataclass(frozen=True)
class StageDescriptor:
    """Один этап конвейера: чем его запускать и как проверять готовность."""

    number: int
    title: str
    run: Callable[[], Awaitable[dict]]
    # Модель слоя N-1 из cascade.PIPELINE_ORDER — preflight требует, чтобы
    # в ней была хотя бы одна строка. None — предусловий нет (вход в
    # цепочку, либо этап сам решает, что делать с пустыми данными).
    requires: type | None
    is_stub: bool
    # Альтернативная точка входа — пересборка уже обработанных данных
    # новыми правилами, без повторного сбора исходных. None у этапов, для
    # которых такой концепции не существует (сегодня — только этап 2).
    run_reparse: Callable[[], Awaitable[dict]] | None = None


async def _run_stub(
    title: str,
    clear: Callable[[AsyncSession], Awaitable[int]],
    seed: Callable[[AsyncSession], Awaitable[int]],
) -> dict:
    """Своя сессия: снести слой -> залить заново -> закоммитить.

    То же самое, что делает `run_stage()` из cascade.py для блока
    `__main__` сидеров, только вызывается из реестра, а не из отдельного
    процесса. Нужно именно clear+seed, а не голый seed: сидеры аддитивны и
    не идемпотентны, повторный запуск без очистки задвоит строки.
    """
    async with AsyncSessionLocal() as session:
        deleted = await clear(session)
        added = await seed(session)
        await session.commit()
    return {'stage': title, 'cleared': deleted, 'added': added}


STAGES: dict[int, StageDescriptor] = {
    1: StageDescriptor(
        number=1,
        title='Сбор (BP-1)',
        run=functools.partial(
            _run_stub,
            'BP-1 (минимальная заглушка raw_item)',
            bp1_stub.clear,
            bp1_stub.seed,
        ),
        requires=None,  # вход в цепочку, предусловий нет
        is_stub=True,
    ),
    2: StageDescriptor(
        number=2,
        title='Нормализация (BP-2)',
        run=run_bp2,
        requires=RawItem,
        is_stub=False,
        run_reparse=functools.partial(run_bp2, reparse=True),
    ),
    3: StageDescriptor(
        number=3,
        title='Категоризация (BP-3)',
        run=run_bp3,
        requires=NormalizedItem,
        is_stub=False,
    ),
    4: StageDescriptor(
        number=4,
        title='Витрина (BP-4)',
        run=run_bp4,
        requires=CategorizedEvent,
        is_stub=False,
    ),
    5: StageDescriptor(
        number=5,
        title='Алертинг (BP-5)',
        run=run_bp5,
        requires=ShowcaseEvent,
        is_stub=False,
    ),
    6: StageDescriptor(
        number=6,
        title='План действий (BP-6)',
        run=run_bp6,
        requires=ShowcaseEvent,
        is_stub=False,
    ),
    7: StageDescriptor(
        number=7,
        title='Источники: перенос кандидатов (BP-7)',
        run=run_bp7_promotion,
        # Наполнение source_candidate теперь реальное — делает
        # SourceFinderModule на этапе 3 (не отдельный подэтап здесь).
        # Своя, независимая цепочка (source_candidate), не часть
        # PIPELINE_ORDER; пустая очередь кандидатов — не ошибка (см.
        # design.md, Decisions), поэтому предусловий нет.
        requires=None,
        is_stub=False,
    ),
}
