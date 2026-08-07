"""`run_stage(n)` — один этап с preflight, `run_all()` — весь конвейер.

`run_all()` не останавливается на первом сбое: каждый этап оборачивается в
свой `try/except`, в конце — сводка по всем семи (см. design.md, Decisions —
"run_all() не прерывается на первом сбое").
"""

from dataclasses import dataclass

from core.database import AsyncSessionLocal
from core.pipeline.registry import STAGES, StageDescriptor
from core.scripts.stages.cascade import count_rows


class UnknownStageError(RuntimeError):
    """Запрошен номер этапа, которого нет в реестре."""


@dataclass
class StageResult:
    number: int
    title: str
    is_stub: bool
    ok: bool
    result: dict | None = None
    error: str | None = None


def _get_stage(number: int) -> StageDescriptor:
    try:
        return STAGES[number]
    except KeyError:
        raise UnknownStageError(
            f'Этапа {number} не существует — доступны 1..{len(STAGES)}'
        ) from None


async def _preflight(descriptor: StageDescriptor) -> None:
    """Проверить, что данные предыдущего слоя есть, иначе — понятная ошибка.

    `requires is None` — либо вход в цепочку (этап 1), либо у этапа своя
    независимая семантика "пусто — не ошибка" (этап 7, см. design.md).
    """
    if descriptor.requires is None:
        return
    async with AsyncSessionLocal() as session:
        rows = await count_rows(session, descriptor.requires)
    if rows == 0:
        raise RuntimeError(
            f'Этап {descriptor.number} ({descriptor.title}): нет данных в '
            f'"{descriptor.requires.__tablename__}" — сначала прогоните '
            'предыдущий этап.'
        )


async def run_stage(number: int) -> StageResult:
    """Запустить один этап: preflight -> вызов -> результат.

    Поднимает `UnknownStageError`/`RuntimeError` — вызывающий код (CLI,
    позже API) решает, как их показать.
    """
    descriptor = _get_stage(number)
    await _preflight(descriptor)
    result = await descriptor.run()
    return StageResult(
        number=descriptor.number,
        title=descriptor.title,
        is_stub=descriptor.is_stub,
        ok=True,
        result=result,
    )


async def run_all() -> list[StageResult]:
    """Прогнать все этапы 1..7 по порядку.

    Сбой (preflight или исключение) одного этапа НЕ прерывает цикл — каждый
    этап в своём `try/except`, чтобы за один прогон было видно полную
    картину конвейера, а не только первую поломку.
    """
    results: list[StageResult] = []
    for number in sorted(STAGES):
        descriptor = STAGES[number]
        try:
            await _preflight(descriptor)
            result = await descriptor.run()
        except Exception as exc:
            results.append(
                StageResult(
                    number=descriptor.number,
                    title=descriptor.title,
                    is_stub=descriptor.is_stub,
                    ok=False,
                    error=str(exc),
                )
            )
        else:
            results.append(
                StageResult(
                    number=descriptor.number,
                    title=descriptor.title,
                    is_stub=descriptor.is_stub,
                    ok=True,
                    result=result,
                )
            )
    return results
