"""Порядок слоёв данных и каскадная очистка — общий помощник этапов.

Все FK в проекте объявлены с ondelete=RESTRICT: база намеренно не даёт снести
строку, на которую кто-то ссылается (история не должна рушиться молча).
Поэтому очистка любого слоя = очистка его самого И всего, что ниже по потоку.

Порядок зависимостей описан ОДИН раз в PIPELINE_ORDER, и все семь модулей
этапов пользуются им через clear_from() — руками перечислять таблицы не надо.

Здесь же run_stage() — общий раннер для блока __main__ каждого этапа:
открыть сессию, снести, залить, закоммитить, напечатать сводку.
"""

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from src.bp1.models import Competitor, RawItem, SearchTask, Source, Trigger
from src.bp2.models import (
    BlackDomain,
    NormalizedItem,
    Region,
    StopWord,
    TopicLimit,
)
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp4.models import ShowcaseEvent
from src.bp5.models import Alert, Channel, EventType, RoutingRule, User
from src.bp6.models import ActionItem
from src.bp7.models import SourceCandidate

# Слои данных пайплайна в порядке «дети → родители»: удалять можно только
# в этом направлении. Индекс модели = её место в цепочке, чем меньше —
# тем дальше вниз по потоку (ближе к витрине и алертам).
PIPELINE_ORDER = (
    ActionItem,  # BP-6
    Alert,  # BP-5
    ShowcaseEvent,  # BP-4
    CategorizedEvent,  # BP-3
    NormalizedItem,  # BP-2
    RawItem,  # BP-1
    SearchTask,  # BP-1 (конфиг задач сбора)
)

# Справочники — тоже «дети → родители». RoutingRule ссылается на event_type,
# user и channel; User ссылается на department; SourceCandidate — на
# competitor. RoutingRule и SourceCandidate поэтому идут первыми, User —
# сразу за RoutingRule (её саму уже можно удалять), но раньше Department
# (на который User ссылается). Region и Competitor удаляются последними:
# на них смотрят данные пайплайна, так что справочники сносим только после
# PIPELINE_ORDER.
DICTIONARY_ORDER = (
    RoutingRule,
    User,
    SourceCandidate,
    EventType,
    Channel,
    Department,
    Category,
    TopicLimit,
    StopWord,
    BlackDomain,
    Trigger,
    Source,
    Competitor,
    Region,
)


async def clear_from(session: AsyncSession, model: type) -> int:
    """Снести слой model и все слои НИЖЕ него по потоку.

    Пример: clear_from(session, NormalizedItem) удалит action_item, alert,
    showcase_event, categorized_event и сам normalized_item — то есть всё,
    что было построено на этих фактах. Сырьё (raw_item) останется.

    Возвращает суммарное число удалённых строк. commit — на вызывающем.
    """
    stop = PIPELINE_ORDER.index(model)
    total = 0
    for layer in PIPELINE_ORDER[: stop + 1]:
        result = await session.execute(delete(layer))
        total += result.rowcount
    return total


async def count_rows(
    session: AsyncSession, model: type, *, active_only: bool = False
) -> int:
    """Сколько строк в таблице (для сводок в конце скриптов).

    active_only=True — считать только активные строки (model.is_active).
    Нужно там, где неактивная строка не годится как признак готовности
    данных — например, search_task для preflight реального сбора этапа 1
    (core/pipeline/runner.py): неактивную задачу AdaptiveRunner всё равно
    пропустит, так что молчаливый успех без единой активной задачи вводил
    бы в заблуждение.
    """
    stmt = select(func.count()).select_from(model)
    if active_only:
        stmt = stmt.where(model.is_active.is_(True))
    return await session.scalar(stmt)


def run_stage(
    title: str,
    clear: Callable[[AsyncSession], Awaitable[int]],
    seed: Callable[[AsyncSession], Awaitable[int]],
) -> None:
    """Запустить этап как самостоятельный скрипт: снести → залить → сводка.

    Обе операции идут в ОДНОЙ транзакции: если сидинг упадёт, откатится и
    очистка — база не останется наполовину пустой. Вызывается из блока
    __main__ каждого модуля этапа.
    """

    async def main() -> None:
        async with AsyncSessionLocal() as session:
            deleted = await clear(session)
            added = await seed(session)
            await session.commit()
        print(f'{title}: удалено {deleted}, добавлено {added}')

    asyncio.run(main())
