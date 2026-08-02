"""Бэкенд хранения: JSONB-файлы на диске.

Реализует BaseStorage для Bronze Layer. Каждый RawDataFile сохраняется
как один JSONB-файл с секциями meta и items.
Текстовый контент (HTML) сохраняется как строка UTF-8.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiofiles

from ..constants import (
    CHECKSUM_LOG_LENGTH,
    DEFAULT_BASE_PATH_RAW,
    ENCODING_UTF8,
    FILE_MODE_READ,
    FILE_MODE_WRITE,
    JSON_GLOB_PATTERN,
    JSON_INDENT,
    JSON_KEY_COMPETITOR,
    JSON_KEY_EXTRA,
    JSON_KEY_FETCHED_AT,
    JSON_KEY_ITEMS,
    JSON_KEY_MEDIA_NAME,
    JSON_KEY_META,
    JSON_KEY_PUBLISHED_AT,
    JSON_KEY_REGION,
    JSON_KEY_SEARCH_TASK_ID,
    JSON_KEY_SOURCE,
    JSON_KEY_SOURCE_REQUEST_URL,
    JSON_KEY_TEXT,
    JSON_KEY_TITLE,
    JSON_KEY_TRIGGER,
    JSON_KEY_URL,
)
from ..core.exceptions import NotFoundError, StorageError
from ..core.interfaces import BaseStorage
from ..core.models import (
    MetaInfo,
    RawDataFile,
    RawDataItem,
)
from ..utils.hashing import compute_sha256
from ..utils.path_generator import PathGenerator

logger = logging.getLogger(__name__)


class DiskBackend(BaseStorage):
    """Хранение сырых данных в JSONB-файлах на диске.

    Структура каталогов: base_path/YYYY/MM/DD/trigger_{id}/raw_{file_id}.json
    Формат файла: { "meta": { ... }, "items": [ ... ] }
    Файлы иммутабельны после записи (кроме поля meta.status).
    """

    def __init__(self, base_path: str = DEFAULT_BASE_PATH_RAW) -> None:
        self._path_gen = PathGenerator(base_path)

    async def save(self, raw_data_file: RawDataFile) -> str:
        """Сохранить RawDataFile в JSONB-файл.

        Вычисляет SHA-256 чексумму содержимого, генерирует путь,
        записывает файл асинхронно через aiofiles.
        Возвращает путь к записанному файлу.

        Args:
            raw_data_file: Модель выгрузки с meta и items.

        Returns:
            Абсолютный путь к сохранённому файлу.
        """
        path = self._path_gen.generate(
            trigger_id=raw_data_file.meta.trigger,
            file_id=str(raw_data_file.raw_id),
            fetched_at=raw_data_file.meta.fetched_at,
        )
        self._path_gen.ensure_parent(path)

        payload = self._serialize(raw_data_file)
        raw_bytes = json.dumps(payload, ensure_ascii=False, indent=JSON_INDENT)

        try:
            async with aiofiles.open(
                path, FILE_MODE_WRITE, encoding=ENCODING_UTF8
            ) as f:
                await f.write(raw_bytes)
        except OSError as e:
            raise StorageError(f'Ошибка записи файла {path}: {e}') from e

        checksum = compute_sha256(raw_bytes.encode(ENCODING_UTF8))
        logger.info(
            'Сохранён файл %s (чексумма: %s...)',
            path,
            checksum[:CHECKSUM_LOG_LENGTH],
        )
        return path

    async def load(self, path: str) -> RawDataFile:
        """Загрузить и десериализовать RawDataFile из JSONB-файла.

        Args:
            path: Путь к файлу на диске.

        Returns:
            Восстановленная модель RawDataFile.

        Raises:
            NotFoundError: Если файл не существует.
            StorageError: При ошибке чтения или парсинга.
        """
        if not await self.exists(path):
            raise NotFoundError(f'Файл не найден: {path}')

        try:
            async with aiofiles.open(
                path,
                FILE_MODE_READ,
                encoding=ENCODING_UTF8,
            ) as f:
                content = await f.read()
        except OSError as e:
            raise StorageError(f'Ошибка чтения файла {path}: {e}') from e

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as e:
            raise StorageError(
                f'Ошибка парсинга JSON в файле {path}: {e}'
            ) from e

        return self._deserialize(payload)

    async def delete(self, path: str) -> bool:
        """Удалить файл по пути. Возвращает True при успехе."""
        try:
            Path(path).unlink(missing_ok=False)
            logger.info('Удалён файл %s', path)
            return True
        except FileNotFoundError:
            return False
        except OSError as e:
            raise StorageError(f'Ошибка удаления файла {path}: {e}') from e

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

    def _serialize(self, raw_data_file: RawDataFile) -> dict[str, Any]:
        """Сериализовать RawDataFile в JSON-совместимый словарь.

        Структура JSONB (эталон):
        {
            "meta": {
                "search_task_id": 1,
                "source": "hh.ru",
                "competitor": "Бегемот",
                "trigger": "Python",
                "source_request_url": "https://hh.ru/search/...",
                "fetched_at": "2026-07-18T10:00:00Z"
            },
            "items": [
                {
                    "url": "https://hh.ru/vacancy/101",
                    "title": "Python-разработчик",
                    "text": "Описание вакансии...",
                    "published_at": "18 июля 2026",
                    "region": "г. Москва",
                    "media_name": null,
                    "extra": {"salary": "150000-200000 руб."}
                }
            ]
        }
        """
        meta = raw_data_file.meta
        return {
            JSON_KEY_META: {
                JSON_KEY_SEARCH_TASK_ID: meta.search_task_id,
                JSON_KEY_SOURCE: meta.source,
                JSON_KEY_COMPETITOR: meta.competitor,
                JSON_KEY_TRIGGER: meta.trigger,
                JSON_KEY_SOURCE_REQUEST_URL: meta.source_request_url,
                JSON_KEY_FETCHED_AT: meta.fetched_at.isoformat(),
            },
            JSON_KEY_ITEMS: [
                {
                    JSON_KEY_URL: item.url,
                    JSON_KEY_TITLE: item.title,
                    JSON_KEY_TEXT: item.text,
                    JSON_KEY_PUBLISHED_AT: item.published_at,
                    JSON_KEY_REGION: item.region,
                    JSON_KEY_MEDIA_NAME: item.media_name,
                    JSON_KEY_EXTRA: item.extra,
                }
                for item in raw_data_file.items
            ],
        }

    def _deserialize(self, payload: dict[str, Any]) -> RawDataFile:
        """Восстановить RawDataFile из JSON-словаря.

        Обратная операция к _serialize: собирает MetaInfo и список
        RawDataItem из секций JSONB-файла.
        """
        meta_section = payload[JSON_KEY_META]
        items_section = payload.get(JSON_KEY_ITEMS, [])

        meta = MetaInfo(
            search_task_id=meta_section[JSON_KEY_SEARCH_TASK_ID],
            source=meta_section[JSON_KEY_SOURCE],
            competitor=meta_section[JSON_KEY_COMPETITOR],
            trigger=meta_section[JSON_KEY_TRIGGER],
            source_request_url=meta_section[JSON_KEY_SOURCE_REQUEST_URL],
            fetched_at=meta_section[JSON_KEY_FETCHED_AT],
        )

        items = [
            RawDataItem(
                url=item[JSON_KEY_URL],
                title=item[JSON_KEY_TITLE],
                text=item[JSON_KEY_TEXT],
                published_at=item.get(JSON_KEY_PUBLISHED_AT),
                region=item.get(JSON_KEY_REGION),
                media_name=item.get(JSON_KEY_MEDIA_NAME),
                extra=item.get(JSON_KEY_EXTRA, {}),
            )
            for item in items_section
        ]

        return RawDataFile(meta=meta, items=items)
