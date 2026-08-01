"""Слой доступа к данным BP-2: все запросы к БД для конвейера очистки.

Методы (по потоку конвейера):
    select_pending_raw_items → снимки под нормализацию (batch)
      └ _select_latest_raw_items → свежий снимок на задачу
    get_raw_item             → снимок по id (точечно)
    load_competitors         → конкуренты для lookup name→id
    load_regions             → регионы для alias-lookup
    load_source_ids          → search_task_id → source_id
    load_black_domains       → домены чёрного списка
    load_stop_words          → стоп-слова / темы
    load_topic_limits        → лимиты антишума
    upsert_normalized_items  → запись с ON CONFLICT (dedup)
    reject_over_limit        → см. antinoise.py

Общий бойлерплейт вынесен в приватные помощники _scalars / _load_active.
Сессия — в self.session (через __init__), методы её не принимают. Транзакцией
(commit/rollback) управляет вызывающий код — здесь только запросы.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from core.enums import RawItemStatus
from src.bp1.models import Competitor, RawItem, SearchTask
from src.bp2.models import (
    BlackDomain,
    NormalizedItem,
    Region,
    StopWord,
    TopicLimit,
)


class Bp2Crud:
    """Репозиторий BP-2: запросы к raw_item, normalized_item и справочникам."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ========================================================================
    #  Общие помощники (убирают дублирование в методах ниже)
    # ========================================================================

    async def _scalars(self, stmt: Select) -> Sequence[Any]:
        """Выполнить select и вернуть список значений первой колонки."""
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def _load_active(self, model: type) -> Sequence[Any]:
        """Все активные (is_active=True) строки справочника model."""
        return await self._scalars(select(model).where(model.is_active))

    # ========================================================================
    #  Отбор входных снимков
    # ========================================================================

    def _select_latest_raw_items(self):
        """raw_item без error, по одному свежему снимку на search_task_id.

        Тай-брейк id DESC: при равном created_at (new и changed пришли в один
        момент) побеждает позже вставленный снимок — у него больше id.
        """
        return (
            select(RawItem)
            .where(RawItem.status != RawItemStatus.error)
            .order_by(
                RawItem.search_task_id,
                RawItem.created_at.desc(),
                RawItem.id.desc(),
            )
            .distinct(RawItem.search_task_id)
            .subquery()
        )

    async def select_pending_raw_items(self) -> Sequence[RawItem]:
        """Свежие снимки, которых ещё нет в normalized_item (NOT EXISTS).

        Результат упорядочен по search_task_id (стабильный вывод).
        """
        latest = aliased(RawItem, self._select_latest_raw_items())
        # NOT EXISTS вешаем ПОВЕРХ подзапроса свежих снимков, а не в его WHERE:
        # иначе отсев шёл бы до выбора свежего и мог поднять устаревший снимок.
        already_normalized = (
            select(NormalizedItem.id)
            .where(NormalizedItem.raw_item_id == latest.id)
            .exists()
        )
        return await self._scalars(
            select(latest)
            .where(~already_normalized)
            .order_by(latest.search_task_id)
        )

    async def select_reparse_raw_items(
        self, raw_item_ids: Sequence[int] | None = None
    ) -> Sequence[RawItem]:
        """Снимки для ПЕРЕРАЗБОРА — в отличие от select_pending_raw_items не

        проверяет NOT EXISTS: сюда попадают и уже нормализованные снимки.

        raw_item_ids=None — переразобрать все свежие снимки (тот же «латест
        на search_task_id», что и в обычном отборе, только без фильтра «уже
        нормализован»). raw_item_ids=[...] — точечный переразбор КОНКРЕТНЫХ
        строк по id напрямую, без редукции «латест на задачу»: пользователь
        просит именно эти снимки, а не последний на их search_task_id (иначе
        запрос старого снимка по id молча вернул бы пусто, если для его
        задачи с тех пор пришёл более новый). error (raw_data=NULL) всё
        равно исключаем — там нечего разбирать.
        """
        if raw_item_ids is not None:
            return await self._scalars(
                select(RawItem)
                .where(RawItem.id.in_(raw_item_ids))
                .where(RawItem.status != RawItemStatus.error)
                .order_by(RawItem.id)
            )
        latest = aliased(RawItem, self._select_latest_raw_items())
        return await self._scalars(
            select(latest).order_by(latest.search_task_id)
        )

    async def get_raw_item(self, raw_item_id: int) -> RawItem | None:
        """Точечная загрузка снимка по id (переразбор конкретной строки)."""
        return await self.session.get(RawItem, raw_item_id)

    # ========================================================================
    #  Справочники для нормализации (lookup competitor / region / source)
    # ========================================================================

    async def load_competitors(self) -> Sequence[Competitor]:
        """Активные конкуренты — для lookup name → competitor_id."""
        return await self._load_active(Competitor)

    async def load_regions(self) -> Sequence[Region]:
        """Все регионы — для alias-lookup lower(raw) в name_aliases."""
        return await self._scalars(select(Region))

    async def load_source_ids(self) -> dict[int, int]:
        """search_task_id → source_id (денормализация source в normalized)."""
        stmt = select(SearchTask.id, SearchTask.source_id)
        result = await self.session.execute(stmt)
        return dict(result.all())

    # ========================================================================
    #  Справочники фильтрации (чёрные домены / стоп-слова / антишум)
    # ========================================================================

    async def load_black_domains(self) -> set[str]:
        """Активные домены чёрного списка — для сверки с media_domain."""
        rows = await self._load_active(BlackDomain)
        return {row.domain for row in rows}

    async def load_stop_words(self) -> Sequence[StopWord]:
        """Активные стоп-слова / темы / ложные срабатывания (phrase + type)."""
        return await self._load_active(StopWord)

    async def load_topic_limits(self) -> Sequence[TopicLimit]:
        """Активные лимиты антишума."""
        return await self._load_active(TopicLimit)

    # ========================================================================
    #  Запись результата + антишум
    # ========================================================================

    async def upsert_normalized_items(
        self,
        rows: Sequence[dict],
        *,
        update: bool = False,
    ) -> None:
        """Вставка normalized_item с дедупом по dedup_key.

        update=False (обычный инкрементальный прогон) — ON CONFLICT DO NOTHING:
        дубль молча пропускается. update=True (переразбор с новыми правилами) —
        ON CONFLICT DO UPDATE: обновляет status/reject_reason у существующей
        строки. commit делает вызывающий код.
        """
        if not rows:
            return
        stmt = pg_insert(NormalizedItem).values(rows)
        if update:
            stmt = stmt.on_conflict_do_update(
                index_elements=['dedup_key'],
                set_={
                    'status': stmt.excluded.status,
                    'reject_reason': stmt.excluded.reject_reason,
                },
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=['dedup_key'])
        await self.session.execute(stmt)
