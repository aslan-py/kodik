"""Реестр этапов конвейера: `{номер -> дескриптор}`.

Единственный источник правды о том, какая функция стоит за каким этапом.
Ничего не реализует сам — только ссылается на уже существующие функции:
`src/bpN/pipeline.py` (реальные этапы) и `core/scripts/stages/*.py`
(заглушки). Заменить заглушку на финальную реализацию, когда она появится, —
значит поменять одну ссылку здесь, форма реестра не меняется.

Этап 1 — первый, у которого есть ОБЕ реализации одновременно: `run` —
настоящий адаптивный сбор (`src/bp1/pipeline.py::run_bp1`), `run_stub` —
заглушка (`core/scripts/stages/bp1_stub`, шесть синтетических новостей).
Какая выполняется — решает `core.config.settings.true_parsing`, с
возможностью разового переопределения (см. `core/pipeline/runner.py`).
У остальных этапов заглушки нет, только основная реализация.

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
from src.bp1.pipeline import run_bp1
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
    # Альтернативная точка входа — заглушка вместо основной реализации.
    # None — у этапа только одна реализация (её is_stub статично описан
    # выше). Сегодня заполнено только у этапа 1: run — настоящий сбор,
    # run_stub — заглушка.
    run_stub: Callable[[], Awaitable[dict]] | None = None
    # requires считается выполненным только при наличии хотя бы одной
    # АКТИВНОЙ строки (model.is_active), а не просто хотя бы одной. Нужно
    # там, где неактивная строка не годится — see cascade.count_rows.
    requires_active: bool = False
    # Заменяет типовое "сначала прогоните предыдущий этап" в ошибке
    # preflight — для этапов, у которых предыдущего этапа в конвейере нет
    # (сегодня — только реальный сбор этапа 1, чинится не прогоном
    # другого этапа, а заведением задач сбора).
    missing_data_hint: str | None = None


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
        run=run_bp1,
        # Реальный BP-1 сам создаёт недостающие SearchTask из активных
        # Source × Competitor до обхода, поэтому пустая таблица задач —
        # допустимое начальное состояние, а не ошибка preflight.
        requires=None,
        is_stub=False,
        run_stub=functools.partial(
            _run_stub,
            'BP-1 (минимальная заглушка raw_item)',
            bp1_stub.clear,
            bp1_stub.seed,
        ),
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
