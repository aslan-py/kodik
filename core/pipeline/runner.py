"""`run_stage(n)` — один этап с preflight, `run_all()` — весь конвейер.

`run_all()` не останавливается на первом сбое: каждый этап оборачивается в
свой `try/except`, в конце — сводка по всем семи (см. design.md, Decisions —
"run_all() не прерывается на первом сбое").

Этап 1 — первый с двумя реализациями (настоящий сбор / заглушка), выбор
между ними решает `_execute()` по `core.config.settings.true_parsing` с
возможностью разового переопределения через параметр `true_parsing`
(приоритетнее настройки — см. design.md изменения connect-real-bp1-parsing,
Decisions). `StageResult.is_stub` отражает ФАКТИЧЕСКИ выполненную
реализацию, а не статичное поле дескриптора.
"""

from dataclasses import dataclass

from core.config import settings
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


def _resolve_use_stub(
    descriptor: StageDescriptor, true_parsing: bool | None
) -> bool:
    """Нужно ли выполнить альтернативную заглушку этапа.

    У этапа без заглушки (`run_stub is None`) вопрос не стоит — всегда
    основная реализация. У этапа с заглушкой: явный `true_parsing`
    переопределяет `settings.true_parsing` разово, `None` — берёт
    настройку. `true_parsing=True` значит "настоящая реализация",
    поэтому заглушка нужна ровно когда итоговое значение — `False`.
    """
    if descriptor.run_stub is None:
        return False
    if true_parsing is None:
        true_parsing = settings.true_parsing
    return not true_parsing


async def _preflight(descriptor: StageDescriptor, *, use_stub: bool) -> None:
    """Проверить, что данные предыдущего слоя есть, иначе — понятная ошибка.

    Заглушка предусловий не имеет никогда — она самодостаточна и создаёт
    нужные ей данные сама. `requires is None` — у оставшихся реализаций
    либо вход в цепочку (этап 1 без заглушки был бы таким же), либо своя
    независимая семантика "пусто — не ошибка" (этап 7, см. design.md).
    """
    if use_stub:
        return
    if descriptor.requires is None:
        return
    async with AsyncSessionLocal() as session:
        rows = await count_rows(
            session, descriptor.requires, active_only=descriptor.requires_active
        )
    if rows == 0:
        hint = (
            descriptor.missing_data_hint or 'сначала прогоните предыдущий этап.'
        )
        raise RuntimeError(
            f'Этап {descriptor.number} ({descriptor.title}): нет данных в '
            f'"{descriptor.requires.__tablename__}" — {hint}'
        )


async def _execute(
    descriptor: StageDescriptor,
    *,
    reparse: bool = False,
    true_parsing: bool | None = None,
) -> tuple[dict, bool]:
    """Выбрать нужную реализацию этапа, прогнать preflight, вызвать её.

    Возвращает (результат, фактически ли выполнена заглушка) — второе
    идёт в `StageResult.is_stub` вместо статичного поля дескриптора.
    """
    if reparse and descriptor.run_reparse is None:
        raise RuntimeError(
            f'Этап {descriptor.number} ({descriptor.title}): '
            'не поддерживает режим пересборки.'
        )
    if true_parsing is False and descriptor.run_stub is None:
        raise RuntimeError(
            f'Этап {descriptor.number} ({descriptor.title}): '
            'не поддерживает режим заглушки.'
        )

    use_stub = _resolve_use_stub(descriptor, true_parsing)
    await _preflight(descriptor, use_stub=use_stub)

    if reparse:
        return await descriptor.run_reparse(), False
    if use_stub:
        return await descriptor.run_stub(), True
    return await descriptor.run(), descriptor.is_stub


async def run_stage(
    number: int,
    *,
    reparse: bool = False,
    true_parsing: bool | None = None,
) -> StageResult:
    """Запустить один этап: preflight -> вызов -> результат.

    `reparse=True` — пересобрать уже обработанные данные этапа новыми
    правилами вместо обычного прогона; поддерживается не всеми этапами
    (см. `StageDescriptor.run_reparse`).

    `true_parsing` — разовое переопределение выбора реализации (настоящая
    /заглушка) для этапов, у которых есть обе (`StageDescriptor.run_stub`).
    `None` — берётся `settings.true_parsing`.

    Поднимает `UnknownStageError`/`RuntimeError` — вызывающий код (CLI,
    админка) решает, как их показать.
    """
    descriptor = _get_stage(number)
    result, is_stub = await _execute(
        descriptor, reparse=reparse, true_parsing=true_parsing
    )
    return StageResult(
        number=descriptor.number,
        title=descriptor.title,
        is_stub=is_stub,
        ok=True,
        result=result,
    )


async def run_all() -> list[StageResult]:
    """Прогнать все этапы 1..7 по порядку.

    Сбой (preflight или исключение) одного этапа НЕ прерывает цикл — каждый
    этап в своём `try/except`, чтобы за один прогон было видно полную
    картину конвейера, а не только первую поломку. Реализация выбирается
    по настройке (`true_parsing=None` — как и при запуске без явного
    переопределения).
    """
    results: list[StageResult] = []
    for number in sorted(STAGES):
        descriptor = STAGES[number]
        try:
            result, is_stub = await _execute(descriptor)
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
                    is_stub=is_stub,
                    ok=True,
                    result=result,
                )
            )
    return results
