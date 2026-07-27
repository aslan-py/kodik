"""Абстрактные интерфейсы хранилищ."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import RawDataFile


class BaseStorage(ABC):
    """Базовый абстрактный класс хранилища."""

    @abstractmethod
    async def save(self, raw_data_file: RawDataFile) -> str:
        """Сохранить данные. Возвращает путь к файлу."""

    @abstractmethod
    async def load(self, path: str) -> RawDataFile:
        """Загрузить данные по пути."""

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Удалить файл по пути."""

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Проверить существование файла."""

    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """Вернуть список файлов по префиксу пути."""


class BaseDeduplicator(ABC):
    """Базовый интерфейс дедупликации."""

    @abstractmethod
    async def is_duplicate(self, identifier: str) -> bool:
        """Проверить, есть ли запись с таким идентификатором."""


class NoOpDeduplicator(BaseDeduplicator):
    """Заглушка — всегда возвращает False."""

    async def is_duplicate(self, identifier: str) -> bool:
        return False
