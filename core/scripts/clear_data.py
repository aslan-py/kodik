"""Очистка базы: данные пайплайна, по флагу — вместе со справочниками.

Запуск (из корня проекта):
    python -m core.scripts.clear_data                      # только данные
    python -m core.scripts.clear_data --with-dictionaries  # и справочники

Без флага справочники остаются: реестр конкурентов, регионы, правила
фильтрации и маршрутизации переживают очистку, и после неё можно сразу
залить данные заново (stages/bp1 и дальше).

С флагом база становится пустой полностью — понадобится прогнать
stages/dictionaries или seed_all.

Порядок удаления задан в core/scripts/stages/cascade.py: сначала «дети»,
потом «родители», иначе FK с ondelete=RESTRICT не пропустят.
"""

import argparse
import asyncio

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.scripts.stages.cascade import (
    DICTIONARY_ORDER,
    PIPELINE_ORDER,
    clear_from,
)


async def clear(with_dictionaries: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        # Данные пайплайна целиком: от плана действий до задач сбора.
        deleted = await clear_from(session, PIPELINE_ORDER[-1])
        print(f'данные пайплайна: удалено {deleted} строк')

        if with_dictionaries:
            await _clear_dictionaries(session)

        await session.commit()

    tail = '' if with_dictionaries else ' (справочники сохранены)'
    print(f'Очистка завершена{tail}.')


async def _clear_dictionaries(session: AsyncSession) -> None:
    """Снести справочники — только после данных, которые на них ссылаются."""
    total = 0
    for model in DICTIONARY_ORDER:
        result = await session.execute(delete(model))
        total += result.rowcount
    print(f'справочники: удалено {total} строк')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--with-dictionaries',
        action='store_true',
        help='удалить и справочники тоже (база станет полностью пустой)',
    )
    args = parser.parse_args()
    asyncio.run(clear(args.with_dictionaries))
