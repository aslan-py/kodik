"""
ResultMerger — объединение и дедупликация результатов чанков.

Собирает результаты анализа отдельных чанков в единый структурированный
ответ: объединяет items, удаляет дубликаты по ключу (url или
title+published_at), усредняет confidence.
"""

from __future__ import annotations

from typing import Any


class ResultMerger:
    """Объединяет результаты из всех чанков."""

    def __init__(
        self,
        dedup_key: str = 'url',
        merge_metadata: bool = True,
    ) -> None:
        """
        Args:
            dedup_key: Поле для дедупликации (по умолчанию ``url``).
            merge_metadata: Объединять ли метаданные из чанков.
        """
        self.dedup_key = dedup_key
        self.merge_metadata = merge_metadata

    def merge(
        self,
        results: list[dict[str, Any]],
        chunk_metadata: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Объединяет результаты из чанков в единый структурированный ответ.

        Args:
            results: Список результатов от каждого чанка.
            chunk_metadata: Метаданные каждого чанка.

        Returns:
            dict:
                - items: list[dict] — объединённый список элементов.
                - metadata: dict — метаданные объединённого результата.
                - confidence: float — общая уверенность.
                - chunks_processed: int — количество обработанных чанков.
                - total_items_found: int — общее количество найденных
                  элементов.
                - duplicate_count: int — количество удалённых дубликатов.
        """
        chunk_metadata = chunk_metadata or []
        all_items: list[dict[str, Any]] = []
        confidences: list[float] = []
        merged_metadata: dict[str, Any] = {}
        merged_selectors: dict[str, Any] = {}
        merged_schema: dict[str, Any] = {}

        for result in results:
            if not isinstance(result, dict):
                continue
            items = result.get('items', [])
            if isinstance(items, list):
                all_items.extend(items)
            confidence = result.get('confidence')
            if isinstance(confidence, int | float):
                confidences.append(float(confidence))
            if self.merge_metadata:
                meta = result.get('metadata')
                if isinstance(meta, dict):
                    merged_metadata.update(meta)
            # Слияние селекторов и схемы из чанков.
            selectors = result.get('selectors')
            if isinstance(selectors, dict):
                merged_selectors.update(selectors)
            schema = result.get('schema')
            if isinstance(schema, dict):
                merged_schema.update(schema)

        # Дедупликация.
        unique_items, duplicate_count = self._deduplicate(all_items)

        # Общая уверенность — среднее арифметическое.
        confidence = (
            round(sum(confidences) / len(confidences), 3)
            if confidences
            else 0.0
        )

        return {
            'items': unique_items,
            'metadata': merged_metadata,
            'selectors': merged_selectors,
            'schema': merged_schema,
            'confidence': confidence,
            'chunks_processed': len(results),
            'total_items_found': len(all_items),
            'duplicate_count': duplicate_count,
        }

    def _deduplicate(
        self, items: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        """Удаляет дубликаты по ключу (url или title+published_at)."""
        seen: set[Any] = set()
        unique: list[dict[str, Any]] = []
        duplicate_count = 0

        for item in items:
            key = self._item_key(item)
            if key is None:
                unique.append(item)
                continue
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
            unique.append(item)

        return unique, duplicate_count

    def _item_key(self, item: dict[str, Any]) -> Any:
        """Вычисляет ключ дедупликации для элемента."""
        if self.dedup_key and item.get(self.dedup_key):
            return item[self.dedup_key]
        # Fallback: title + published_at.
        title = item.get('title')
        published = item.get('published_at')
        if title:
            return (title, published)
        return None
