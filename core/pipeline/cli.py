"""Минимальный CLI поверх раннера этапов — без лишних флагов/подкоманд.

Использование:
    python -m core.pipeline.cli <номер>          — запустить этап (1..7)
    python -m core.pipeline.cli <номер> reparse  — с пересборкой (если есть)
    python -m core.pipeline.cli <номер> stub     — заглушкой (если есть)
    python -m core.pipeline.cli <номер> real     — настоящей реализацией
                                                    (если есть заглушка)
    python -m core.pipeline.cli all               — весь конвейер
"""

import asyncio
import sys

from core.database import AsyncSessionLocal
from core.enums import PipelineRunKind, PipelineRunSource
from core.pipeline.runner import StageResult, run_all, run_stage
from core.pipeline.service import PipelineRunConflict, PipelineRunService


def _print_result(r: StageResult) -> None:
    stub = ' [ЗАГЛУШКА]' if r.is_stub else ''
    if r.ok:
        print(f'  {r.number}. {r.title}{stub}: OK — {r.result}')
    else:
        print(f'  {r.number}. {r.title}{stub}: ОШИБКА — {r.error}')


async def _main(argv: list[str]) -> int:
    direct = '--direct' in argv
    argv = [arg for arg in argv if arg != '--direct']
    if len(argv) not in (1, 2):
        print(__doc__)
        return 1

    arg = argv[0]
    if arg == 'all':
        if len(argv) != 1:
            print(__doc__)
            return 1
        if not direct:
            try:
                async with AsyncSessionLocal() as session:
                    created = await PipelineRunService(session).enqueue_run(
                        kind=PipelineRunKind.all,
                        source=PipelineRunSource.cli,
                    )
            except PipelineRunConflict as exc:
                print(f'Pipeline is already running: {exc.run_id}')
                return 2
            print(f'Queued pipeline run: {created.run_id}')
            return 0
        results = await run_all()
        print('Сводка по прогону всего конвейера:')
        for r in results:
            _print_result(r)
        return 0 if all(r.ok for r in results) else 1

    try:
        number = int(arg)
    except ValueError:
        print(__doc__)
        return 1

    reparse = False
    true_parsing: bool | None = None
    if len(argv) == 2:
        mode = argv[1]
        if mode == 'reparse':
            reparse = True
        elif mode == 'stub':
            true_parsing = False
        elif mode == 'real':
            true_parsing = True
        else:
            print(__doc__)
            return 1

    if not direct:
        if number not in range(1, 8):
            print(f'Unknown pipeline stage: {number}')
            return 1
        if reparse and number != 2:
            print('reparse is supported only by BP2')
            return 1
        if true_parsing is not None and number != 1:
            print('stub/real is supported only by BP1')
            return 1
        try:
            async with AsyncSessionLocal() as session:
                created = await PipelineRunService(session).enqueue_run(
                    kind=PipelineRunKind.single,
                    stage=number,
                    source=PipelineRunSource.cli,
                    parameters={
                        'reparse': reparse,
                        'true_parsing': true_parsing,
                    },
                )
        except PipelineRunConflict as exc:
            print(f'Pipeline is already running: {exc.run_id}')
            return 2
        print(f'Queued pipeline run: {created.run_id}')
        return 0

    try:
        result = await run_stage(
            number, reparse=reparse, true_parsing=true_parsing
        )
    except Exception as exc:  # неизвестный номер / preflight / сбой этапа
        print(f'Ошибка: {exc}')
        return 1

    _print_result(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
