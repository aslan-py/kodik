# raw_storage

Bronze Layer модуль для хранения сырых данных в ETL-пайплайне конкурентной разведки. Надёжно сохраняет необработанные данные (HTML, JSON, PDF и т.д.) с метаданными источника, триггера и статусом обработки.

## Установка

Зависимости уже включены в корневой `requirements.txt`:

```bash
pip install -r requirements.txt
```

Требования: Python 3.12+, Pydantic 2.0+, aiofiles 23.0+.

## Быстрый старт

```python
import asyncio
from raw_storage import (
    RawData, RawDataRepository, StorageFactory,
    SourceInfo, TriggerInfo, RequestInfo, ContentInfo,
)

async def main():
    # Создаём бэкенд и репозиторий
    backend = StorageFactory.create("disk", base_path="data/raw")
    repo = RawDataRepository(storage_backend=backend)

    # Формируем данные
    raw = RawData(
        source=SourceInfo(type="web", name="kad.arbitr.ru", url="https://kad.arbitr.ru/"),
        trigger=TriggerInfo(id="7743659519", type="inn", name="Поиск по ИНН 7743659519"),
        request=RequestInfo(http_status=200),
        content=ContentInfo(data=b"<html>...</html>", content_type="text/html", format="html"),
    )

    # Сохраняем
    path = await repo.save(raw)
    print(f"Сохранён: {path}")

    # Загружаем обратно
    loaded = await backend.load(path)
    print(f"Чексумма: {loaded.storage.checksum_sha256[:16]}...")

asyncio.run(main())
```

## API

### `StorageFactory`

Фабрика для создания бэкендов хранения.

```python
backend = StorageFactory.create("disk", base_path="data/raw")
```

| Метод | Описание |
|-------|----------|
| `create(backend_type, **kwargs)` | Создать экземпляр бэкенда по строке |
| `register(name, backend_class)` | Зарегистрировать новый бэкенд |

### `RawDataRepository`

Репозиторий — основная точка входа для работы с данными.

| Метод | Описание |
|-------|----------|
| `save(raw_data) -> str` | Сохранить данные с проверкой дедупликации |
| `find_by_id(raw_id) -> RawData` | Найти запись по UUID |
| `find_by_trigger(trigger_id) -> list[RawData]` | Найти все записи по триггеру |
| `find_pending() -> list[RawData]` | Найти записи со статусом PENDING |
| `update_status(raw_id, status, error?)` | Обновить статус обработки |
| `delete(path) -> bool` | Удалить файл |

### `RawData`

Основная модель Bronze Layer.

| Секция | Модель | Описание |
|--------|--------|----------|
| `source` | `SourceInfo` | Тип, имя и URL источника |
| `trigger` | `TriggerInfo` | ID, тип, имя и ключевые слова триггера |
| `request` | `RequestInfo` | HTTP-статус и заголовки |
| `content` | `ContentInfo` | Байты, MIME-тип, формат, кодировка |
| `storage` | `StorageInfo` | Путь на диске и SHA-256 чексумма |
| `processing` | `ProcessingInfo` | Статус (PENDING → PROCESSING → DONE/ERROR) |

### `ProcessingStatus`

| Значение | Описание |
|----------|----------|
| `PENDING` | Запись создана, обработка не начата |
| `PROCESSING` | Идёт обработка (Silver Layer) |
| `DONE` | Обработка завершена |
| `ERROR` | Ошибка при обработке |

## Структура

```
raw_storage/
├── __init__.py              # Экспорт публичного API
├── constants.py             # Константы (пути, JSON-ключи, кодировки)
├── factory.py               # StorageFactory
├── core/
│   ├── interfaces.py        # ABC: BaseStorage, BaseDeduplicator, NoOpDeduplicator
│   ├── models.py            # Pydantic модели (RawData и секции)
│   └── exceptions.py        # StorageError, NotFoundError, ValidationError
├── backends/
│   └── disk_backend.py      # DiskBackend: JSON на диске (async, aiofiles)
├── services/
│   └── repository.py        # RawDataRepository
└── utils/
    ├── hashing.py           # compute_sha256()
    └── path_generator.py    # PathGenerator (YYYY/MM/DD/trigger_{id}/raw_{id}.json)
```

## Хранение

### DiskBackend

Данные сохраняются в JSON-файлы с иерархической структурой каталогов:

```
data/raw/
└── 2026/
    └── 07/
        └── 20/
            └── trigger_7743659519/
                └── raw_c3066f57-....json
```

Структура JSON-файла:

```json
{
  "source": { "type": "web", "name": "kad.arbitr.ru", "url": "..." },
  "trigger": { "id": "7743659519", "type": "inn", "name": "...", "keywords": [...] },
  "request": { "http_status": 200, "headers": {} },
  "content": { "data": "...", "content_type": "text/html", "format": "html", "encoding": "utf-8" },
  "storage": { "path": "...", "checksum_sha256": "..." },
  "processing": { "status": "pending", "cleaned_at": null, "category": null, "error": null },
  "metadata": { "raw_id": "...", "crawled_at": "..." }
}
```

Бинарные данные (PDF, изображения) кодируются в base64 с `encoding: "base64"`.

## Дедупликация

Модуль поддерживает дедупликацию через внедряемый `BaseDeduplicator`. По умолчанию используется `NoOpDeduplicator` (всегда `False`). Для интеграции:

```python
from raw_storage.core.interfaces import BaseDeduplicator

class ChecksumDeduplicator(BaseDeduplicator):
    async def is_duplicate(self, checksum: str) -> bool:
        # Реализация: проверка по индексу или БД
        ...

repo = RawDataRepository(
    storage_backend=backend,
    deduplicator=ChecksumDeduplicator(),
)
```

## Исключения

| Исключение | Описание |
|------------|----------|
| `StorageError` | Базовое исключение модуля |
| `NotFoundError` | Файл не найден по пути |
| `ValidationError` | Ошибка валидации данных |
| `DeduplicationError` | Ошибка при проверке дубликатов |

## Расширение

Добавить новый бэкенд (S3, GCS, SQL):

1. Реализуйте `BaseStorage` из `raw_storage.core.interfaces`
2. Зарегистрируйте в фабрике:

```python
from raw_storage import StorageFactory
from my_backends import S3Backend

StorageFactory.register("s3", S3Backend)
backend = StorageFactory.create("s3", bucket="my-bucket")
```
