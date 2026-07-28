"""Ядро модуля raw_storage: модели, интерфейсы, исключения."""

from .exceptions import NotFoundError, StorageError, ValidationError
from .interfaces import BaseDeduplicator, BaseStorage, NoOpDeduplicator
from .models import (
    MetaInfo,
    ProcessingStatus,
    RawDataFile,
    RawDataItem,
)

__all__ = [
    'BaseDeduplicator',
    'BaseStorage',
    'MetaInfo',
    'NoOpDeduplicator',
    'NotFoundError',
    'ProcessingStatus',
    'RawDataFile',
    'RawDataItem',
    'StorageError',
    'ValidationError',
]
