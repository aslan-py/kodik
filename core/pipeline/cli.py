"""Минимальный CLI поверх раннера этапов — без лишних флагов/подкоманд.

Использование:
    python -m core.pipeline.cli <номер>          — запустить этап (1..7)
    python -m core.pipeline.cli <номер> reparse  — с пересборкой (если есть)
    python -m core.pipeline.cli all               — весь конвейер
"""

import asyncio
import sys

from core.pipeline.runner import StageResult, run_all, run_stage


def _print_result(r: StageResult) -> None:
    stub = ' [ЗАГЛУШКА]' if r.is_stub else ''
    if r.ok:
        print(f'  {r.number}. {r.title}{stub}: OK — {r.result}')
    else:
        print(f'  {r.number}. {r.title}{stub}: ОШИБКА — {r.error}')


async def _main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print(__doc__)
        return 1

    arg = argv[0]
    if arg == 'all':
        if len(argv) != 1:
            print(__doc__)
            return 1
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
    if len(argv) == 2:
        if argv[1] != 'reparse':
            print(__doc__)
            return 1
        reparse = True

    try:
        result = await run_stage(number, reparse=reparse)
    except Exception as exc:  # неизвестный номер / preflight / сбой этапа
        print(f'Ошибка: {exc}')
        return 1

    _print_result(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
