"""Слой доступа к данным BP-4: запросы витрины.

Методы (по потоку конвейера):
    select_pending_events   → размеченные события под сборку витрины
    upsert_showcase_events  → запись строк витрины (ON CONFLICT DO UPDATE)

Справочники отдельными методами не грузим (в отличие от BP-2): здесь все
связи уже через FK, поэтому имена подтягиваются джойнами в самом SELECT.

Сессия — в self.session (через __init__), методы её не принимают. Транзакцией
(commit/rollback) управляет вызывающий код — здесь только запросы.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Row, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.enums import NormStatus
from src.bp1.models import Competitor
from src.bp2.models import NormalizedItem, Region
from src.bp3.models import CategorizedEvent, Category, Department
from src.bp4.models import ShowcaseEvent

# Колонки, которые при конфликте НЕ перезаписываем значениями из VALUES:
# id — свой у строки витрины; categorized_event_id — сам ключ конфликта;
# updated_at — ставим отдельно через func.now() (см. upsert_showcase_events).
_UPSERT_SKIP = frozenset({'id', 'categorized_event_id', 'updated_at'})


class Bp4Crud:
    """Репозиторий BP-4: отбор размеченных событий и запись витрины."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    #  Отбор входных событий
    # ========================================================================

    async def select_pending_events(self) -> Sequence[Row[Any]]:
        """Размеченные события, которым нужна строка витрины.

        Один запрос отдаёт всё, из чего собирается плоская строка: смыслы
        (CategorizedEvent), факты (NormalizedItem) и ИМЕНА из справочников
        вместо id. category джойнится обычным JOIN (category_id NOT NULL),
        остальные — LEFT JOIN: отдел, конкурент и регион могут быть NULL.

        Отбор инкрементальный, два случая:
          - строки витрины ещё нет                        → новое событие;
          - categorized_at > showcase_event.updated_at    → BP-3 переразметил
            уже опубликованное событие, витрину надо обновить.

        Фильтр status='ok' обязателен: антишум BP-2 (reject_over_limit)
        помечает rejected уже вставленные строки, и событие могло стать
        шумом уже ПОСЛЕ того, как BP-3 его разметил. Без фильтра шум
        просочился бы в витрину.

        Возвращает Row'ы вида (CategorizedEvent, NormalizedItem,
        category_name, department_name, competitor_name, region_name,
        macro_region, latitude, longitude) — ровно сигнатура
        build_showcase_row.
        """
        stmt = (
            select(
                CategorizedEvent,
                NormalizedItem,
                Category.name.label('category_name'),
                Department.name.label('department_name'),
                Competitor.name.label('competitor_name'),
                Region.name_display.label('region_name'),
                Region.macro_region.label('macro_region'),
                Region.latitude.label('latitude'),
                Region.longitude.label('longitude'),
            )
            .join(
                NormalizedItem,
                NormalizedItem.id == CategorizedEvent.normalized_item_id,
            )
            .join(Category, Category.id == CategorizedEvent.category_id)
            .outerjoin(
                Department, Department.id == CategorizedEvent.department_id
            )
            .outerjoin(
                Competitor, Competitor.id == NormalizedItem.competitor_id
            )
            .outerjoin(Region, Region.id == NormalizedItem.region_id)
            .outerjoin(
                ShowcaseEvent,
                ShowcaseEvent.categorized_event_id == CategorizedEvent.id,
            )
            .where(NormalizedItem.status == NormStatus.ok)
            .where(
                or_(
                    ShowcaseEvent.id.is_(None),
                    CategorizedEvent.categorized_at > ShowcaseEvent.updated_at,
                )
            )
            .order_by(CategorizedEvent.id)
        )
        result = await self.session.execute(stmt)
        return result.all()

    # ========================================================================
    #  Запись витрины
    # ========================================================================

    async def upsert_showcase_events(self, rows: Sequence[dict]) -> int:
        """Инкрементальная запись витрины: INSERT … ON CONFLICT DO UPDATE.

        Ключ конфликта — categorized_event_id (UNIQUE): одна строка витрины
        на размеченное событие. Новое событие вставляется, переразмеченное
        перезаписывается — полной перезагрузки витрины не бывает (требование
        ТЗ BP-4).

        updated_at проставляем ЯВНО и на вставку, и на обновление:

        - onupdate в модели — это ORM-хук, при INSERT … ON CONFLICT он не
          срабатывает, и отметка времени осталась бы прежней;
        - server_default=now() тоже не подходит: в Postgres now() — время
          НАЧАЛА транзакции, а не момента выполнения. Если BP-3 и BP-4 идут
          в одной транзакции (так делает сидер), витрина получила бы
          updated_at РАНЬШЕ categorized_at и навсегда осталась «устаревшей».

        Поэтому берём datetime.now(UTC) на момент записи — тот же приём, что
        в default моделей. Иначе условие отбора (categorized_at > updated_at)
        срабатывало бы вечно и строка пересобиралась бы на каждом прогоне.

        Возвращает число затронутых строк. commit делает вызывающий код.
        """
        if not rows:
            return 0

        now = datetime.now(UTC)
        stmt = pg_insert(ShowcaseEvent).values(
            [{**row, 'updated_at': now} for row in rows]
        )
        updatable = {
            name: stmt.excluded[name]
            for name in rows[0]
            if name not in _UPSERT_SKIP
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=['categorized_event_id'],
            set_={**updatable, 'updated_at': now},
        )
        result = await self.session.execute(stmt)
        return result.rowcount
