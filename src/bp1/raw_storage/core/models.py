"""Pydantic v2 модели данных для Bronze Layer.

Модели формируют контракт между слоями ETL-пайплайна:
- SourceInfo — откуда пришли данные
- TriggerInfo — что запустило сбор
- RequestInfo — параметры HTTP-запроса
- ContentInfo — сами данные и их формат
- StorageInfo — где лежит файл и его чексумма
- ProcessingInfo — статус обработки
- RawData — агрегированная модель, объединяющая все секции
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from raw_storage.constants import ENCODING_UTF8


class ProcessingStatus(str, Enum):
    """Статус обработки сырых данных.

    Lifecycle: PENDING -> PROCESSING -> DONE | ERROR
    """

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class SourceInfo(BaseModel):
    """Информация об источнике данных (сайт, API, файл)."""

    type: str = Field(description="Тип источника (web, api, file)")
    name: str = Field(description="Читаемое название источника")
    url: str = Field(description="URL или путь к источнику")


class TriggerInfo(BaseModel):
    """Информация о триггере — что инициировало сбор данных.

    Триггер определяет контекст: по какому ИНН искали,
    какой запрос отправляли и т.д.
    """

    id: str = Field(description="Уникальный ID триггера")
    type: str = Field(description="Тип триггера (inn, keyword, url)")
    name: str = Field(description="Отображаемое имя триггера")
    keywords: list[str] = Field(
        default_factory=list, description="Ключевые слова для поиска"
    )


class RequestInfo(BaseModel):
    """Параметры HTTP-запроса к источнику."""

    http_status: int = Field(description="HTTP статус-код ответа")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Заголовки ответа"
    )


class ContentInfo(BaseModel):
    """Содержимое ответа: сырые данные, тип и кодировка.

    Бинарные данные (PDF, изображения) кодируются в base64 при сериализации.
    Текстовые (HTML, JSON) сохраняются как есть.
    """

    data: bytes = Field(description="Сырые байты контента")
    content_type: str = Field(
        description="MIME-тип (text/html, application/json)")
    format: str = Field(description="Формат данных (html, json, pdf, png)")
    encoding: str = Field(
        default=ENCODING_UTF8, description="Кодировка: utf-8 или base64"
    )


class StorageInfo(BaseModel):
    """Метаданные хранения: путь на диске и целостность данных."""

    path: str = Field(description="Абсолютный или относительный путь к файлу")
    checksum_sha256: str = Field(
        description="SHA-256 хеш контента для целостности")


class ProcessingInfo(BaseModel):
    """Состояние обработки записи в ETL-пайплайне.

    После записи JSON-файл считается иммутабельным,
    кроме поля status — оно обновляется при смене стадии.
    """

    status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING,
        description="Текущий статус обработки",
    )
    cleaned_at: datetime | None = Field(
        default=None,
        description="Время очистки (Silver Layer), если прошла",
    )
    category: dict | None = Field(
        default=None,
        description="Категория данных после классификации",
    )
    error: str | None = Field(
        default=None,
        description="Описание ошибки, если статус ERROR",
    )


class RawData(BaseModel):
    """Основная модель Bronze Layer — контракт для всех данных.

    Содержит полную информацию о собранном объекте:
    источник, триггер, запрос, контент, хранилище и статус обработки.
    """

    raw_id: UUID = Field(
        default_factory=uuid4, description="Уникальный ID записи"
    )
    source: SourceInfo = Field(description="Откуда пришли данные")
    trigger: TriggerInfo = Field(description="Что запустило сбор")
    request: RequestInfo = Field(description="HTTP-метаданные запроса")
    content: ContentInfo = Field(description="Сырые данные и их формат")
    storage: StorageInfo | None = Field(
        default=None,
        description="Путь и чексумма (заполняется после сохранения)",
    )
    processing: ProcessingInfo = Field(
        default_factory=ProcessingInfo,
        description="Статус обработки в пайплайне",
    )
    crawled_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp сбора данных",
    )
