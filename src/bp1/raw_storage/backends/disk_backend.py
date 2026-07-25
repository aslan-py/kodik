"""Бэкенд хранения: JSON-файлы на диске.

Реализует BaseStorage для Bronze Layer. Каждый RawData сохраняется
как один самодостаточный JSON-файл с вложенными секциями.
Бинарный контент (PDF, изображения) кодируется в base64.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import aiofiles
from raw_storage.constants import (
    CHECKSUM_LOG_LENGTH,
    DEFAULT_BASE_PATH,
    ENCODING_ASCII,
    ENCODING_BASE64,
    ENCODING_UTF8,
    FILE_MODE_READ,
    FILE_MODE_WRITE,
    JSON_GLOB_PATTERN,
    JSON_INDENT,
    JSON_KEY_CATEGORY,
    JSON_KEY_CHECKSUM,
    JSON_KEY_CLEANED_AT,
    JSON_KEY_CONTENT,
    JSON_KEY_CONTENT_TYPE,
    JSON_KEY_CRAWLED_AT,
    JSON_KEY_DATA,
    JSON_KEY_ERROR,
    JSON_KEY_FORMAT,
    JSON_KEY_HEADERS,
    JSON_KEY_HTTP_STATUS,
    JSON_KEY_ID,
    JSON_KEY_KEYWORDS,
    JSON_KEY_METADATA,
    JSON_KEY_NAME,
    JSON_KEY_PATH,
    JSON_KEY_PROCESSING,
    JSON_KEY_RAW_ID,
    JSON_KEY_REQUEST,
    JSON_KEY_SOURCE,
    JSON_KEY_STATUS,
    JSON_KEY_STORAGE,
    JSON_KEY_TRIGGER,
    JSON_KEY_TYPE,
    JSON_KEY_URL,
)
from raw_storage.core.exceptions import NotFoundError, StorageError
from raw_storage.core.interfaces import BaseStorage
from raw_storage.core.models import (
    ContentInfo,
    ProcessingInfo,
    RawData,
    RequestInfo,
    SourceInfo,
    StorageInfo,
    TriggerInfo,
)
from raw_storage.utils.hashing import compute_sha256
from raw_storage.utils.path_generator import PathGenerator

logger = logging.getLogger(__name__)


class DiskBackend(BaseStorage):
    """Хранение сырых данных в JSON-файлах на диске.

    Структура каталогов: base_path/YYYY/MM/DD/trigger_{id}/raw_{id}.json
    Файлы иммутабельны после записи (кроме поля status).
    """

    def __init__(self, base_path: str = DEFAULT_BASE_PATH) -> None:
        self._path_gen = PathGenerator(base_path)

    async def save(self, raw_data: RawData) -> str:
        """Сохранить RawData в JSON-файл.

        Вычисляет SHA-256 чексумму контента, генерирует путь,
        записывает файл асинхронно через aiofiles.
        Возвращает путь к записанному файлу.
        """
        path = self._path_gen.generate(
            trigger_id=raw_data.trigger.id,
            raw_id=str(raw_data.raw_id),
            crawled_at=raw_data.crawled_at,
        )
        self._path_gen.ensure_parent(path)

        # Вычисляем чексумму и привязываем к записи
        checksum = compute_sha256(raw_data.content.data)
        raw_data.storage = StorageInfo(path=path, checksum_sha256=checksum)

        payload = self._serialize(raw_data)
        try:
            async with aiofiles.open(
                path, FILE_MODE_WRITE, encoding=ENCODING_UTF8
            ) as f:
                await f.write(
                    json.dumps(payload, ensure_ascii=False, indent=JSON_INDENT)
                )
        except OSError as e:
            raise StorageError(f"Ошибка записи файла {path}: {e}") from e

        logger.info(
            "Сохранён файл %s (чексумма: %s...)",
            path,
            checksum[:CHECKSUM_LOG_LENGTH],
        )
        return path

    async def load(self, path: str) -> RawData:
        """Загрузить и десериализовать RawData из JSON-файла."""
        if not await self.exists(path):
            raise NotFoundError(f"Файл не найден: {path}")

        try:
            async with aiofiles.open(
                path,
                FILE_MODE_READ,
                encoding=ENCODING_UTF8
            ) as f:
                content = await f.read()
        except OSError as e:
            raise StorageError(f"Ошибка чтения файла {path}: {e}") from e

        payload = json.loads(content)
        return self._deserialize(payload)

    async def delete(self, path: str) -> bool:
        """Удалить файл по пути. Возвращает True при успехе."""
        try:
            Path(path).unlink(missing_ok=False)
            logger.info("Удалён файл %s", path)
            return True
        except FileNotFoundError:
            return False
        except OSError as e:
            raise StorageError(f"Ошибка удаления файла {path}: {e}") from e

    async def exists(self, path: str) -> bool:
        """Проверить, что файл существует на диске."""
        return Path(path).is_file()

    async def list(self, prefix: str) -> list[str]:
        """Рекурсивно найти все .json файлы по префиксу каталога.

        Если prefix пустой — сканирует корень хранилища (base_path).
        """
        root = Path(prefix) if prefix else self._path_gen._base
        if not root.is_dir():
            return []
        return [str(p) for p in root.rglob(JSON_GLOB_PATTERN)]

    def _serialize(self, raw_data: RawData) -> dict[str, Any]:
        """Сериализовать RawData в JSON-совместимый словарь.

        Бинарный контент кодируется в base64, текстовый — сохраняется как UTF-8
        строка.
        Структура JSON: source / trigger / request / content / storage /
                        processing / metadata.
        """
        content = raw_data.content

        # Определяем кодировку контента
        try:
            text = content.data.decode(ENCODING_UTF8)
            encoding = ENCODING_UTF8
            data_value = text
        except UnicodeDecodeError:
            encoding = ENCODING_BASE64
            data_value = base64.b64encode(content.data).decode(ENCODING_ASCII)

        return {
            JSON_KEY_SOURCE: {
                JSON_KEY_TYPE: raw_data.source.type,
                JSON_KEY_NAME: raw_data.source.name,
                JSON_KEY_URL: raw_data.source.url,
            },
            JSON_KEY_TRIGGER: {
                JSON_KEY_ID: raw_data.trigger.id,
                JSON_KEY_TYPE: raw_data.trigger.type,
                JSON_KEY_NAME: raw_data.trigger.name,
                JSON_KEY_KEYWORDS: raw_data.trigger.keywords,
            },
            JSON_KEY_REQUEST: {
                JSON_KEY_HTTP_STATUS: raw_data.request.http_status,
                JSON_KEY_HEADERS: raw_data.request.headers,
            },
            JSON_KEY_CONTENT: {
                JSON_KEY_DATA: data_value,
                JSON_KEY_CONTENT_TYPE: content.content_type,
                JSON_KEY_FORMAT: content.format,
                # Поле encoding показывает, как декодировать data
                "encoding": encoding,
            },
            JSON_KEY_STORAGE: {
                JSON_KEY_PATH: (
                    raw_data.storage.path if raw_data.storage else ""
                ),
                JSON_KEY_CHECKSUM: raw_data.storage.checksum_sha256
                if raw_data.storage
                else "",
            },
            JSON_KEY_PROCESSING: {
                JSON_KEY_STATUS: raw_data.processing.status.value,
                JSON_KEY_CLEANED_AT: (
                    raw_data.processing.cleaned_at.isoformat()
                    if raw_data.processing.cleaned_at
                    else None
                ),
                JSON_KEY_CATEGORY: raw_data.processing.category,
                JSON_KEY_ERROR: raw_data.processing.error,
            },
            JSON_KEY_METADATA: {
                JSON_KEY_RAW_ID: str(raw_data.raw_id),
                JSON_KEY_CRAWLED_AT: raw_data.crawled_at.isoformat(),
            },
        }

    def _deserialize(self, payload: dict[str, Any]) -> RawData:
        """Восстановить RawData из JSON-словаря.

        Обратная операция к _serialize: декодирует base64 при необходимости,
        собирает вложенные Pydantic-модели из секций JSON.
        """
        content_section = payload[JSON_KEY_CONTENT]
        encoding = content_section.get("encoding", ENCODING_UTF8)

        # Декодируем контент в зависимости от кодировки
        if encoding == ENCODING_BASE64:
            data = base64.b64decode(content_section[JSON_KEY_DATA])
        else:
            data = content_section[JSON_KEY_DATA].encode(ENCODING_UTF8)

        proc = payload.get(JSON_KEY_PROCESSING, {})
        storage_sec = payload.get(JSON_KEY_STORAGE, {})
        meta = payload.get(JSON_KEY_METADATA, {})

        return RawData(
            raw_id=meta[JSON_KEY_RAW_ID],
            source=SourceInfo(**payload[JSON_KEY_SOURCE]),
            trigger=TriggerInfo(**payload[JSON_KEY_TRIGGER]),
            request=RequestInfo(**payload[JSON_KEY_REQUEST]),
            content=ContentInfo(
                data=data,
                content_type=content_section[JSON_KEY_CONTENT_TYPE],
                format=content_section[JSON_KEY_FORMAT],
                encoding=encoding,
            ),
            storage=(
                StorageInfo(
                    path=storage_sec.get(JSON_KEY_PATH, ""),
                    checksum_sha256=storage_sec.get(JSON_KEY_CHECKSUM, ""),
                )
                if storage_sec.get(JSON_KEY_PATH)
                else None
            ),
            processing=ProcessingInfo(
                status=proc.get(JSON_KEY_STATUS, "pending"),
                cleaned_at=proc.get(JSON_KEY_CLEANED_AT),
                category=proc.get(JSON_KEY_CATEGORY),
                error=proc.get(JSON_KEY_ERROR),
            ),
            crawled_at=meta[JSON_KEY_CRAWLED_AT],
        )
