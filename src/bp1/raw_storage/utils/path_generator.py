"""Генерация путей для хранения файлов.

Формат пути: base_path/YYYY/MM/DD/trigger_{id}/raw_{id}.json
Директории создаются по годам/месяцам/дням для удобства навигации.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from raw_storage.constants import (
    DEFAULT_BASE_PATH,
    FILE_EXTENSION,
    RAW_FILE_PREFIX,
    TRIGGER_DIR_PREFIX,
)


class PathGenerator:
    """Генерирует пути для JSON-файлов на диске.

    Использует иерархическую структуру по дате для организации файлов.
    Каждый триггер получает свою директорию.
    """

    def __init__(self, base_path: str = DEFAULT_BASE_PATH) -> None:
        self._base = Path(base_path)

    def generate(
        self,
        trigger_id: str,
        raw_id: str,
        crawled_at: datetime | None = None,
    ) -> str:
        """Сгенерировать полный путь к JSON-файлу.

        Args:
            trigger_id: ID триггера (формирует имя директории)
            raw_id: ID записи (формирует имя файла)
            crawled_at: Дата сбора (определяет путь YYYY/MM/DD)

        Returns:
            Строка с полным путем, например:
            data/raw/2026/07/20/trigger_abc123/raw_def456.json
        """
        dt = crawled_at or datetime.now()
        path = (
            self._base
            / str(dt.year)
            / f"{dt.month:02d}"
            / f"{dt.day:02d}"
            / f"{TRIGGER_DIR_PREFIX}{trigger_id}"
            / f"{RAW_FILE_PREFIX}{raw_id}{FILE_EXTENSION}"
        )
        return str(path)

    def ensure_parent(self, path: str) -> None:
        """Создать все родительские директории, если их еще нет.

        Args:
            path: Полный путь к файлу (родители будут созданы рекурсивно)
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
