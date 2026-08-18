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
        acc: dict[str, Any] = {
            'items': [],
            'confidences': [],
            'metadata': {},
            'selectors': {},
            'schema': {},
        }
        for result in results:
            self._accumulate_result(result, acc)

        # Дедупликация.
        unique_items, duplicate_count = self._deduplicate(acc['items'])

        # Общая уверенность — среднее арифметическое.
        confidences = acc['confidences']
        confidence = (
            round(sum(confidences) / len(confidences), 3)
            if confidences
            else 0.0
        )

        return {
            'items': unique_items,
            'metadata': acc['metadata'],
            'selectors': acc['selectors'],
            'schema': acc['schema'],
            'confidence': confidence,
            'chunks_processed': len(results),
            'total_items_found': len(acc['items']),
            'duplicate_count': duplicate_count,
        }

    def _accumulate_result(self, result: Any, acc: dict[str, Any]) -> None:
        """Добавляет один результат чанка в аккумулятор ``merge``."""
        if not isinstance(result, dict):
            return
        items = result.get('items', [])
        if isinstance(items, list):
            acc['items'].extend(items)
        confidence = result.get('confidence')
        if isinstance(confidence, int | float):
            acc['confidences'].append(float(confidence))
        if self.merge_metadata:
            meta = result.get('metadata')
            if isinstance(meta, dict):
                acc['metadata'].update(meta)
        # Слияние селекторов и схемы из чанков.
        # Непустые значения имеют приоритет: если один чанк вернул
        # пустой селектор для поля, а другой — непустой, берём непустой.
        self._merge_dict_field(result, 'selectors', acc['selectors'])
        self._merge_dict_field(result, 'schema', acc['schema'])

    @staticmethod
    def _merge_dict_field(
        result: dict[str, Any], field: str, target: dict[str, Any]
    ) -> None:
        """Копирует непустые значения ``result[field]`` в ``target``."""
        value = result.get(field)
        if not isinstance(value, dict):
            return
        for key, val in value.items():
            if val and not target.get(key):
                target[key] = val

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
