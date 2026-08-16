"""Реализации дедупликации Bronze Layer.

``BaseDeduplicator`` (``core/interfaces.py``) — абстрактный контракт
(``is_duplicate(identifier) -> bool``). Здесь — конкретная реализация,
используемая ``RawDataRepository`` по умолчанию вместо прежней заглушки
``NoOpDeduplicator`` (всегда возвращала ``False``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from .interfaces import BaseDeduplicator


class ContentHashDeduplicator(BaseDeduplicator):
    """Дедупликация по хешу содержимого items (не по ``raw_id``).

    ``RawDataFile.raw_id`` — всегда свежий случайный UUID при
    конструировании (``core/models.py``, ``default_factory=uuid4``),
    поэтому совпадение по нему практически никогда не происходит.
    Реальный смысл имеет дубликат по содержимому: та же выгрузка
    (тот же набор items) сохраняется повторно, например при ретрае.
    ``identifier``, передаваемый в ``is_duplicate()`` — это хеш
    содержимого items (``utils.hashing.compute_items_hash``), не ``raw_id``.

    Не реализует поиск существующего файла самостоятельно — принимает
    готовую lookup-функцию (обычно
    ``RawDataRepository.find_by_content_hash``), чтобы не дублировать
    логику сканирования хранилища, которая уже есть в репозитории
    (``find_by_id``/``find_by_trigger``/``find_pending``).
    """

    def __init__(
        self, find_by_hash: Callable[[str], Awaitable[str | None]]
    ) -> None:
        self._find_by_hash = find_by_hash

    async def is_duplicate(self, identifier: str) -> bool:
        """True, если файл с таким хешем содержимого items уже сохранён."""
        return await self._find_by_hash(identifier) is not None
