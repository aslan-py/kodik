"""Единый сидинг: справочники и демо-данные по всему пайплайну BP-1…BP-6.

Оркестратор: своих данных не держит, а прогоняет по очереди этапы из
core/scripts/stages — те же модули, которые можно запускать поодиночке.
Так логика заполнения каждого слоя существует в одном экземпляре.

Запуск (из корня проекта):
    python -m core.scripts.seed_all

Идемпотентен по справочникам (ON CONFLICT DO NOTHING), но НЕ по данным:
каждый этап сначала чистит свой слой. То есть повторный запуск полностью
пересобирает пайплайн, а справочники оставляет как есть.

Нужен только один слой — запускай этап напрямую:
    python -m core.scripts.stages.bp3
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.scripts.stages import bp1, bp2, bp3, bp4, bp5, bp6, dictionaries
from core.scripts.stages.cascade import (
    DICTIONARY_ORDER,
    PIPELINE_ORDER,
    clear_from,
    count_rows,
)

# Порядок обязателен: каждый следующий этап строится на предыдущем.
STAGES = (
    ('справочники', dictionaries),
    ('BP-1 сырьё', bp1),
    ('BP-2 факты', bp2),
    ('BP-3 разметка', bp3),
    ('BP-4 витрина', bp4),
    ('BP-5 алерты', bp5),
    ('BP-6 план действий', bp6),
)


async def print_summary(session: AsyncSession) -> None:
    """Сколько строк получилось в каждой таблице — справочники и данные."""
    print('\nГотово. Строк в таблицах:')
    for model in reversed(DICTIONARY_ORDER + PIPELINE_ORDER):
        count = await count_rows(session, model)
        print(f'  {model.__tablename__:22} {count}')


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Данные пайплайна сносим ОДИН раз здесь, а не в каждом этапе:
        # иначе bp2 снёс бы то, что только что залил bp1.
        await clear_from(session, PIPELINE_ORDER[-1])

        for title, stage in STAGES:
            added = await stage.seed(session)
            print(f'{title:22} +{added}')

        await session.commit()
        await print_summary(session)


if __name__ == '__main__':
    asyncio.run(seed())
