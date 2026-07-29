"""Фабрика для создания бэкендов хранения."""

from __future__ import annotations

from src.bp1.raw_storage.backends.disk_backend import DiskBackend
from src.bp1.raw_storage.core.exceptions import StorageError
from src.bp1.raw_storage.core.interfaces import BaseStorage


class StorageFactory:
    """Создаёт бэкенд по строке из конфигурации."""

    _registry: dict[str, type[BaseStorage]]

    @classmethod
    def _get_registry(cls) -> dict[str, type[BaseStorage]]:
        """Ленивая инициализация реестра бэкендов."""
        if not hasattr(cls, '_registry'):
            cls._registry = {
                'disk': DiskBackend,
            }
        return cls._registry

    @classmethod
    def create(
        cls, backend_type: str = 'disk', **kwargs: object
    ) -> BaseStorage:
        """Создать экземпляр бэкенда."""
        registry = cls._get_registry()
        if backend_type not in registry:
            available = ', '.join(registry.keys())
            raise StorageError(
                f"Неизвестный бэкенд '{backend_type}'. Доступные: {available}",
            )
        return registry[backend_type](**kwargs)

    @classmethod
    def register(cls, name: str, backend_class: type[BaseStorage]) -> None:
        """Зарегистрировать новый бэкенд."""
        cls._get_registry()[name] = backend_class
