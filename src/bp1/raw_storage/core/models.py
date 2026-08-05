"""Pydantic v2 модели данных для Bronze Layer (JSONB-формат).

Модели описывают структуру JSONB-файла выгрузки:
- MetaInfo — метаданные выгрузки (откуда, когда, статус)
- RawDataItem — один элемент данных внутри выгрузки
- RawDataFile — корневая структура: meta + items
- ProcessingStatus — статус обработки в ETL-пайплайне
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    """Статус обработки сырых данных.

    Жизненный цикл: PENDING -> PROCESSING -> DONE | ERROR
    """

    PENDING = 'pending'
    PROCESSING = 'processing'
    DONE = 'done'
    ERROR = 'error'


class MetaInfo(BaseModel):
    """Метаданные выгрузки — секция meta JSONB-файла.

    Содержит информацию о том, откуда, когда и в рамках какой задачи
    были собраны данные.
    """

    search_task_id: int = Field(description='ID поисковой задачи в БД')
    source: str = Field(
        description='Код источника (hh.ru, fedresurs.ru)',
    )
    competitor: str = Field(description='Наименование конкурента')
    trigger: str = Field(
        description='Идентификатор триггера (ИНН, ключевое слово)',
    )
    source_request_url: str = Field(
        description='URL исходного запроса к источнику',
    )
    fetched_at: datetime = Field(
        description='Timestamp выгрузки (время получения данных)',
    )


class RawDataItem(BaseModel):
    """Один элемент данных внутри выгрузки — элемент массива items.

    Содержит URL, заголовок, полный текст/HTML и дополнительные
    структурированные поля, извлечённые при сборе.
    """

    url: str = Field(description='URL конкретного элемента')
    title: str = Field(description='Заголовок элемента')
    text: str = Field(description='Полный текст или HTML-код элемента')
    published_at: str | None = Field(
        default=None,
        description=('Сырая дата строкой (имя = колонке); BP-2 парсит в date'),
    )
    region: str | None = Field(
        default=None,
        description=(
            'Сырое имя региона (не id) -> lookup в region -> region_id'
        ),
    )
    media_name: str | None = Field(
        default=None,
        description=(
            'Имя публикатора (имя = колонке): у hh пусто, у новостей = СМИ'
        ),
    )
    extra: dict = Field(
        default_factory=dict,
        description=(
            'Источник-специфичные СЫРЫЕ факты; {} если их нет. '
            'У hh здесь зарплата -> нормализуется в '
            'extra.salary_from/salary_to/currency'
        ),
    )


class RawDataFile(BaseModel):
    """Корневая модель JSONB-файла выгрузки.

    Хранит метаданные выгрузки (meta) и массив собранных элементов (items).
    Один файл = одна выгрузка / одна страница результатов.
    """

    raw_id: UUID = Field(
        default_factory=uuid4,
        description='Уникальный ID файла выгрузки',
    )
    meta: MetaInfo = Field(description='Метаданные выгрузки')
    items: list[RawDataItem] = Field(
        default_factory=list,
        description='Массив собранных элементов',
    )
