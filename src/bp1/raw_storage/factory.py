"""Фабрика для создания бэкендов хранения."""

from __future__ import annotations

from raw_storage.backends.disk_backend import DiskBackend
from raw_storage.core.exceptions import StorageError
from raw_storage.core.interfaces import BaseStorage


class StorageFactory:
    """Создаёт бэкенд по строке из конфигурации."""

    _registry: dict[str, type[BaseStorage]] = {
        "disk": DiskBackend,
    }

    @classmethod
    def create(cls, backend_type: str = "disk", **kwargs) -> BaseStorage:
        """Создать экземпляр бэкенда."""
        if backend_type not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise StorageError(
                f"Неизвестный бэкенд '{backend_type}'. Доступные: {available}"
            )
        return cls._registry[backend_type](**kwargs)

    @classmethod
    def register(cls, name: str, backend_class: type[BaseStorage]) -> None:
        """Зарегистрировать новый бэкенд."""
        cls._registry[name] = backend_class
