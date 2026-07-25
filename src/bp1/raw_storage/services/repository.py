"""Сервисный слой — Repository для работы с сырыми данными.

Точка входа для всего ETL-пайплайна: сохранение, поиск,
обновление статуса и удаление записей Bronze Layer.
Использует паттерн Repository с внедрением зависимостей.
"""

from __future__ import annotations

import logging
from uuid import UUID

from raw_storage.constants import CHECKSUM_LOG_LENGTH
from raw_storage.core.exceptions import NotFoundError, StorageError
from raw_storage.core.interfaces import (
    BaseDeduplicator,
    BaseStorage,
    NoOpDeduplicator,
)
from raw_storage.core.models import ProcessingStatus, RawData

logger = logging.getLogger(__name__)


class RawDataRepository:
    """Репозиторий для операций с сырыми данными Bronze Layer.

    Предоставляет CRUD-операции и поиск по атрибутам.
    Поддерживает дедупликацию через внедряемый BaseDeduplicator.
    Все операции асинхронные для интеграции с asyncio-пайплайнами.
    """

    def __init__(
        self,
        storage_backend: BaseStorage,
        deduplicator: BaseDeduplicator | None = None,
    ) -> None:
        """
        Args:
            storage_backend: Реализация хранилища (DiskBackend, S3Backend, ...)
            deduplicator: Проверяль дубликатов (по умолчанию NoOpDeduplicator)
        """
        self._storage = storage_backend
        self._dedup = deduplicator or NoOpDeduplicator()

    async def save(self, raw_data: RawData) -> str:
        """Сохранить данные с проверкой дедупликации.

        Если чексумма уже есть в модели — использует её.
        Иначе вычисляет SHA-256 от контента.
        При обнаружении дубликата возвращает путь существующего файла
        или выбрасывает StorageError, если пути нет.

        Returns:
            Путь к сохранённому JSON-файлу
        """
        # Используем существующую чексумму или вычисляем новую
        if raw_data.storage and raw_data.storage.checksum_sha256:
            checksum = raw_data.storage.checksum_sha256
        else:
            from raw_storage.utils.hashing import compute_sha256

            checksum = compute_sha256(raw_data.content.data)

        # Проверяем дедупликацию
        if await self._dedup.is_duplicate(checksum):
            logger.info(
                "Дубликат обнаружен (чексумма: %s...), пропуск",
                checksum[:CHECKSUM_LOG_LENGTH],
            )
            if raw_data.storage:
                return raw_data.storage.path
            raise StorageError("Дубликат без storage path")

        path = await self._storage.save(raw_data)
        logger.info("RawData %s сохранён в %s", raw_data.raw_id, path)
        return path

    async def find_by_id(self, raw_id: UUID | str) -> RawData:
        """Найти запись по уникальному raw_id.

        Сканирует все файлы в хранилище — для частых запросов
        рекомендуется индекс или кэш.
        """
        results = await self.find_by_prefix("")
        for path in results:
            data = await self._storage.load(path)
            if str(data.raw_id) == str(raw_id):
                return data
        raise NotFoundError(f"Запись {raw_id} не найдена")

    async def find_by_trigger(self, trigger_id: str) -> list[RawData]:
        """Найти все записи, собранные по указанному триггеру."""
        results = []
        for path in await self.find_by_prefix(""):
            data = await self._storage.load(path)
            if data.trigger.id == trigger_id:
                results.append(data)
        return results

    async def find_pending(self) -> list[RawData]:
        """Найти все записи со статусом PENDING.

        Используется для восстановления прерванной обработки
        или запуска нового этапа Silver Layer.
        """
        results = []
        for path in await self.find_by_prefix(""):
            data = await self._storage.load(path)
            if data.processing.status.value == "pending":
                results.append(data)
        return results

    async def update_status(
        self,
        raw_id: UUID | str,
        status: str | ProcessingStatus,
        error: str | None = None,
    ) -> None:
        """Обновить статус обработки записи.

        Перезаписывает JSON-файл с обновлённым статусом.
        Это единственное допустимое изменение иммутабельного файла.

        Args:
            raw_id: ID записи
            status: Новый статус (строка или ProcessingStatus)
            error: Сообщение об ошибке (при статусе ERROR)
        """
        data = await self.find_by_id(raw_id)
        data.processing.status = (
            ProcessingStatus(status) if isinstance(status, str) else status
        )
        if error:
            data.processing.error = error
        await self._storage.save(data)
        logger.info(
            "Статус %s обновлён на %s", raw_id, data.processing.status.value
        )

    async def find_by_prefix(self, prefix: str = "") -> list[str]:
        """Вернуть список путей файлов по префиксу каталога.

        Если prefix пустой — сканирует весь корень хранилища.
        """
        return await self._storage.list(prefix)

    async def delete(self, path: str) -> bool:
        """Удалить файл по пути. Возвращает True при успехе."""
        return await self._storage.delete(path)
