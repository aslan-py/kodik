"""Конвейер BP-4: размеченные события → плоская витрина showcase_event.

Схлопывает два слоя в одну широкую строку под BI: ФАКТЫ из normalized_item
(BP-2) и СМЫСЛЫ из categorized_event (BP-3). id справочников заменяются
именами, enum'ы — подписями, поэтому BI читает витрину без единого джойна.

Порядок шагов:

  1. отобрать события под сборку — select_pending_events (crud)
  2. собрать плоскую строку (имена вместо id) — build_showcase_row
  3. записать инкрементально — upsert_showcase_events (crud)

Отбор инкрементальный: новое событие ИЛИ переразмеченное после публикации
(подробности — в докстроке select_pending_events). Полной перезагрузки
витрины не бывает — требование ТЗ BP-4.

Две точки входа: sync_showcase(session) — шаги 1-3 в ЧУЖОЙ сессии, без
commit (используется сидером); run_bp4() — самостоятельный прогон со своей
сессией и commit.

Соседние модули: crud.py — БД; constants.py — подписи приоритета/тональности;
models.py — таблица витрины.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from src.bp4.constants import PRIORITY_DISPLAY, TONALITY_DISPLAY
from src.bp4.crud import Bp4Crud

# ============================================================================
#  Сборка одной строки витрины
# ============================================================================


def build_showcase_row(row: Sequence[Any]) -> dict:
    """Строка выборки BP-4 → dict под вставку в showcase_event.

    Ожидает кортеж в порядке select_pending_events: (CategorizedEvent,
    NormalizedItem, category_name, department_name, competitor_name,
    region_name, macro_region, latitude, longitude). Имена справочников
    приходят уже готовыми из джойнов — здесь только раскладываем их по
    колонкам витрины и переводим enum'ы в подписи («p1» → «П1»,
    «positive» → «позитивная»).

    raw_item_id берём из фактов: он обеспечивает drill-down от строки
    витрины до исходного снимка (требование прозрачности ТЗ).

    Чистая функция: ни сессии, ни запросов — только перекладывание полей.
    """
    (
        event,
        item,
        category,
        department,
        competitor,
        region,
        macro_region,
        latitude,
        longitude,
    ) = row
    return {
        'categorized_event_id': event.id,
        'raw_item_id': item.raw_item_id,
        # ---- ФАКТЫ (BP-2) ----
        'published_at': item.published_at,
        'title': item.title,
        'media': item.media_name,
        'region': region,
        'macro_region': macro_region,
        # Координаты центра региона — метка на карте рынка в BI.
        'latitude': latitude,
        'longitude': longitude,
        'competitor': competitor,
        'source_url': item.url,
        # ---- СМЫСЛЫ (BP-3) ----
        'priority': PRIORITY_DISPLAY[event.priority],
        'category': category,
        'tonality': TONALITY_DISPLAY[event.tonality],
        'media_index': event.media_index,
        'action': event.action,
        'deadline': event.deadline,
        'department': department,
        'comment': event.comment,
    }


# ============================================================================
#  Оркестратор — весь конвейер BP-4 в один прогон (шаги помечены ниже)
# ============================================================================


async def sync_showcase(session: AsyncSession) -> dict:
    """Синхронизировать витрину в переданной сессии (без commit).

    Вынесено отдельно от run_bp4, чтобы сборку витрины можно было выполнить
    внутри чужой транзакции — так её вызывает сидер (core/scripts/seed_all.py),
    не открывая вторую сессию и не коммитя посреди своей.

    Возвращает сводку прогона: сколько событий отобрано и сколько строк
    витрины затронуто.
    """
    crud = Bp4Crud(session)

    # Шаг 1 — отобрать новые и переразмеченные события
    pending = await crud.select_pending_events()

    # Шаг 2 — собрать плоские строки (имена вместо id, подписи вместо enum'ов)
    rows = [build_showcase_row(row) for row in pending]

    # Шаг 3 — записать инкрементально (ON CONFLICT DO UPDATE)
    upserted = await crud.upsert_showcase_events(rows)

    return {'pending': len(pending), 'upserted': upserted}


async def run_bp4() -> dict:
    """Один самостоятельный прогон конвейера BP-4: разметка → витрина.

    Открывает свою сессию, синхронизирует витрину и коммитит.
    Возвращает сводку прогона (сколько событий обработано).
    """
    async with AsyncSessionLocal() as session:
        summary = await sync_showcase(session)
        await session.commit()
        return summary


# import asyncio

# if __name__ == '__main__':
#     # python -m src.bp4.pipeline
#     result = asyncio.run(run_bp4())
#     print(result)
