"""Кастомные исключения модуля raw_storage."""


class StorageError(Exception):
    """Базовое исключение модуля хранения."""


class NotFoundError(StorageError):
    """Файл не найден по указанному пути."""


class ValidationError(StorageError):
    """Ошибка валидации данных."""


class DeduplicationError(StorageError):
    """Ошибка при проверке дедупликации."""
