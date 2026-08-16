"""Сервисный слой — Repository для работы с файлами выгрузок.

Точка входа для всего ETL-пайплайна: сохранение, поиск,
обновление статуса и удаление JSONB-файлов Bronze Layer.
Использует паттерн Repository с внедрением зависимостей.
"""

from __future__ import annotations

import logging
from uuid import UUID

from ..constants import CHECKSUM_LOG_LENGTH
from ..core.deduplication import ContentHashDeduplicator
from ..core.exceptions import DeduplicationError, NotFoundError
from ..core.interfaces import BaseDeduplicator, BaseStorage
from ..core.models import ProcessingStatus, RawDataFile
from ..utils.hashing import compute_items_hash

logger = logging.getLogger(__name__)


class RawDataRepository:
    """Репозиторий для операций с JSONB-файлами выгрузок Bronze Layer.

    Предоставляет CRUD-операции и поиск по атрибутам meta.
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
            deduplicator: Проверяльщик дубликатов (по умолчанию
                ContentHashDeduplicator — дедупликация по хешу содержимого
                items, см. core/deduplication.py)
        """
        self._storage = storage_backend
        self._dedup = deduplicator or ContentHashDeduplicator(
            self.find_by_content_hash
        )

    async def save(self, raw_data_file: RawDataFile) -> str:
        """Сохранить файл выгрузки с проверкой дедупликации.

        Дедупликация выполняется по хешу содержимого items
        (utils.hashing.compute_items_hash), а не по raw_id: каждый
        RawDataFile получает свежий случайный raw_id при конструировании
        (core/models.py), поэтому совпадение по нему практически никогда
        не происходит — реальный смысл имеет дубликат по содержимому (та
        же выгрузка сохраняется повторно, например при ретрае).
        При обнаружении дубликата возвращает путь существующего файла
        или выбрасывает DeduplicationError, если пути нет (несогласованное
        состояние: дедупликатор сообщил о дубликате, а файл не найден).

        Args:
            raw_data_file: Модель выгрузки с meta и items.

        Returns:
            Путь к сохранённому JSONB-файлу.
        """
        content_hash = compute_items_hash(
            [item.model_dump() for item in raw_data_file.items]
        )

        if await self._dedup.is_duplicate(content_hash):
            logger.info(
                'Дубликат обнаружен (хеш содержимого: %s...), пропуск',
                content_hash[:CHECKSUM_LOG_LENGTH],
            )
            existing = await self.find_by_content_hash(content_hash)
            if existing is not None:
                return existing
            raise DeduplicationError(
                f'Дубликат (хеш содержимого {content_hash}) без '
                'существующего файла',
            )

        path = await self._storage.save(raw_data_file)
        logger.info('RawDataFile %s сохранён в %s', raw_data_file.raw_id, path)
        return path

    async def find_by_content_hash(self, content_hash: str) -> str | None:
        """Найти путь к файлу с указанным хешем содержимого items.

        В отличие от find_by_id, не бросает NotFoundError при отсутствии
        совпадения — возвращает None, т.к. используется в проверке
        дубликатов (ContentHashDeduplicator), где «не найдено» — обычный
        исход, а не ошибка.

        Сканирует все файлы в хранилище — для частых запросов
        рекомендуется индекс или кэш (как и у find_by_id/find_pending).
        """
        for path in await self.find_by_prefix(''):
            data = await self._storage.load(path)
            data_hash = compute_items_hash(
                [item.model_dump() for item in data.items]
            )
            if data_hash == content_hash:
                return path
        return None

    async def find_by_id(self, raw_id: UUID | str) -> str:
        """Найти путь к файлу выгрузки по уникальному raw_id.

        Сканирует все файлы в хранилище — для частых запросов
        рекомендуется индекс или кэш.

        Args:
            raw_id: UUID или строка с ID файла выгрузки.

        Returns:
            Путь к файлу на диске.

        Raises:
            NotFoundError: Если файл с таким raw_id не найден.
        """
        results = await self.find_by_prefix('')
        for path in results:
            data = await self._storage.load(path)
            if str(data.raw_id) == str(raw_id):
                return path
        raise NotFoundError(f'Файл выгрузки {raw_id} не найден')

    async def find_by_trigger(self, trigger_id: str) -> list[RawDataFile]:
        """Найти все выгрузки, собранные по указанному триггеру.

        Args:
            trigger_id: Идентификатор триггера (например, ИНН).

        Returns:
            Список моделей RawDataFile, соответствующих триггеру.
        """
        results: list[RawDataFile] = []
        for path in await self.find_by_prefix(''):
            data = await self._storage.load(path)
            if data.meta.trigger == trigger_id:
                results.append(data)
        return results

    async def find_pending(self) -> list[RawDataFile]:
        """Найти все выгрузки со статусом PENDING.

        Используется для восстановления прерванной обработки
        или запуска нового этапа Silver Layer.

        Returns:
            Список моделей RawDataFile со статусом PENDING.
        """
        results: list[RawDataFile] = []
        for path in await self.find_by_prefix(''):
            data = await self._storage.load(path)
            if data.meta.status == ProcessingStatus.PENDING:
                results.append(data)
        return results

    async def update_status(
        self,
        raw_id: UUID | str,
        status: str | ProcessingStatus,
        error: str | None = None,
    ) -> None:
        """Обновить статус обработки выгрузки.

        Загружает файл, обновляет meta.status и перезаписывает.
        Это единственное допустимое изменение иммутабельного файла.

        Args:
            raw_id: ID файла выгрузки.
            status: Новый статус (строка или ProcessingStatus).
            error: Сообщение об ошибке (при статусе ERROR).
        """
        path = await self.find_by_id(raw_id)
        data = await self._storage.load(path)

        new_status = (
            ProcessingStatus(status) if isinstance(status, str) else status
        )
        data.meta.status = new_status

        # Перезаписываем файл с обновлённым статусом
        await self._storage.save(data)
        logger.info(
            'Статус выгрузки %s обновлён на %s',
            raw_id,
            new_status.value,
        )

    async def find_by_prefix(self, prefix: str = '') -> list[str]:
        """Вернуть список путей файлов по префиксу каталога.

        Если prefix пустой — сканирует весь корень хранилища.
        """
        return await self._storage.list(prefix)

    async def delete(self, path: str) -> bool:
        """Удалить файл по пути. Возвращает True при успехе."""
        return await self._storage.delete(path)
