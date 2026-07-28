"""Генерация путей для хранения файлов выгрузок.

Формат пути: base_path/YYYY/MM/DD/trigger_{id}/raw_{file_id}.json
Директории создаются по годам/месяцам/дням для удобства навигации.
Один файл = одна выгрузка (JSONB-формат: meta + items).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..constants import (
    DEFAULT_BASE_PATH,
    FILE_EXTENSION,
    RAW_FILE_PREFIX,
    TRIGGER_DIR_PREFIX,
)


class PathGenerator:
    """Генерирует пути для JSONB-файлов выгрузок на диске.

    Использует иерархическую структуру по дате для организации файлов.
    Каждый триггер получает свою директорию.
    """

    def __init__(self, base_path: str = DEFAULT_BASE_PATH) -> None:
        self._base = Path(base_path)

    def generate(
        self,
        trigger_id: str,
        file_id: str,
        fetched_at: datetime | None = None,
    ) -> str:
        """Сгенерировать полный путь к JSONB-файлу выгрузки.

        Args:
            trigger_id: ID триггера (формирует имя директории)
            file_id: ID файла выгрузки (формирует имя файла)
            fetched_at: Время выгрузки (определяет путь YYYY/MM/DD)

        Returns:
            Строка с полным путем, например:
            data/raw/2026/07/20/trigger_6318034066/raw_a1b2c3d4.json
        """
        dt = fetched_at or datetime.now()
        path = (
            self._base
            / str(dt.year)
            / f'{dt.month:02d}'
            / f'{dt.day:02d}'
            / f'{TRIGGER_DIR_PREFIX}{trigger_id}'
            / f'{RAW_FILE_PREFIX}{file_id}{FILE_EXTENSION}'
        )
        return str(path)

    def ensure_parent(self, path: str) -> None:
        """Создать все родительские директории, если их еще нет.

        Args:
            path: Полный путь к файлу (родители будут созданы рекурсивно)
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
