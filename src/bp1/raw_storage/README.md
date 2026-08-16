# raw_storage

Bronze Layer модуль для хранения сырых данных в ETL-пайплайне конкурентной разведки. Сохраняет необработанные данные (HTML, JSON и т.д.) в JSONB-формате: один файл = одна выгрузка/страница с метаданными (meta) и массивом элементов (items).

## Статус: ✅ РАБОТАЕТ

Пакет протестирован с реальными HTML-файлами (620 КБ каждый):
- Сохранение 4 HTML-файлов в JSONB-формат — **успешно**
- Загрузка и десериализация обратно — **успешно**
- Целостность HTML-контента после цикла save/load — **подтверждена**
- Структура JSONB (`meta` + `items`) — **корректна**

## Как работать

### 1. Создать выгрузку (RawDataFile)

```python
from datetime import datetime, timezone, timedelta
from raw_storage import RawDataFile, MetaInfo, RawDataItem

tz = timezone(timedelta(hours=5))

batch = RawDataFile(
    meta=MetaInfo(
        search_task_id=1,  # ID задачи в БД
        source='fedresurs.ru',  # код источника
        competitor='ООО СИТИГРАД',  # наименование конкурента
        trigger='6318034066',  # ИНН / ключевое слово
        source_request_url='https://fedresurs.ru/company/6318034066',
        fetched_at=datetime.now(tz),  # время выгрузки
    ),
    items=[
        RawDataItem(
            url='https://fedresurs.ru/sfactmessages/123',
            title='Недостоверность сведений',
            text='<!DOCTYPE html><html>...</html>',  # полный HTML
            published_at='07.07.2026',  # сырая дата строкой
            region=None,
            media_name=None,  # СМИ/публикатор
            extra={},  # источник-специфичные поля (напр. зарплата у hh)
        ),
    ],
)
```

### 2. Сохранить на диск

```python
from raw_storage import StorageFactory, RawDataRepository

backend = StorageFactory.create('disk', base_path='data/raw')
repo = RawDataRepository(storage_backend=backend)

path = await repo.save(batch)
print(f'Сохранён: {path}')
# data/raw/2026/07/27/trigger_6318034066/raw_a1b2c3d4-....json
```

### 3. Загрузить обратно

```python
loaded = await backend.load(path)
print(f'Элементов: {len(loaded.items)}')
print(f'Источник: {loaded.meta.source}')
print(f'Статус: {loaded.meta.status.value}')
```

### 4. Найти выгрузки по триггеру

```python
results = await repo.find_by_trigger('6318034066')
for r in results:
    print(f'{r.meta.fetched_at}: {len(r.items)} элементов')
```

### 5. Обновить статус обработки

```python
from raw_storage import ProcessingStatus

await repo.update_status(
    raw_id=batch.raw_id,
    status=ProcessingStatus.DONE,
)
```

## Установка

Зависимости уже включены в корневой `requirements.txt`:

```bash
pip install -r requirements.txt
```

Требования: Python 3.12+, Pydantic 2.0+, aiofiles 23.0+.

## Быстрый старт (полный пример)

```python
import asyncio
from datetime import datetime, timezone, timedelta
from raw_storage import (
    RawDataFile,
    RawDataItem,
    MetaInfo,
    RawDataRepository,
    StorageFactory,
)


async def main():
    # Создаём бэкенд и репозиторий
    backend = StorageFactory.create('disk', base_path='data/raw')
    repo = RawDataRepository(storage_backend=backend)

    # Формируем выгрузку
    tz = timezone(timedelta(hours=5))
    batch = RawDataFile(
        meta=MetaInfo(
            search_task_id=1,
            source='fedresurs.ru',
            competitor='ООО СИТИГРАД',
            trigger='6318034066',
            source_request_url='https://fedresurs.ru/company/...',
            fetched_at=datetime.now(tz),
        ),
        items=[
            RawDataItem(
                url='https://fedresurs.ru/sfactmessages/...',
                title='Недостоверность сведений',
                text='<!DOCTYPE html><html>...</html>',
                published_at='07.07.2026',
            ),
        ],
    )

    # Сохраняем
    path = await repo.save(batch)
    print(f'Сохранён: {path}')

    # Загружаем обратно
    loaded = await backend.load(path)
    print(f'Элементов: {len(loaded.items)}')


asyncio.run(main())
```

## API

### `StorageFactory`

Фабрика для создания бэкендов хранения.

```python
backend = StorageFactory.create('disk', base_path='data/raw')
```

| Метод | Описание |
|-------|----------|
| `create(backend_type, **kwargs)` | Создать экземпляр бэкенда по строке |
| `register(name, backend_class)` | Зарегистрировать новый бэкенд |

### `RawDataRepository`

Репозиторий — основная точка входа для работы с выгрузками.

| Метод | Описание |
|-------|----------|
| `save(raw_data_file) -> str` | Сохранить выгрузку с проверкой дедупликации |
| `find_by_id(raw_id) -> str` | Найти путь к файлу по UUID выгрузки |
| `find_by_trigger(trigger_id) -> list[RawDataFile]` | Найти все выгрузки по триггеру |
| `find_pending() -> list[RawDataFile]` | Найти выгрузки со статусом PENDING |
| `update_status(raw_id, status, error?)` | Обновить статус обработки |
| `delete(path) -> bool` | Удалить файл |

### `RawDataFile`

Корневая модель JSONB-файла выгрузки.

| Поле | Тип | Описание |
|------|-----|----------|
| `raw_id` | `UUID` | Уникальный ID файла выгрузки |
| `meta` | `MetaInfo` | Метаданные выгрузки |
| `items` | `list[RawDataItem]` | Массив собранных элементов |

### `MetaInfo`

Метаданные выгрузки — секция `meta` JSONB-файла.

| Поле | Тип | Описание |
|------|-----|----------|
| `search_task_id` | `int` | ID поисковой задачи в БД |
| `source` | `str` | Код источника (fedresurs.ru, kad-arbitr.ru) |
| `competitor` | `str` | Наименование конкурента |
| `trigger` | `str` | Идентификатор триггера (ИНН, ключевое слово) |
| `source_request_url` | `str` | URL исходного запроса к источнику |
| `fetched_at` | `datetime` | Timestamp выгрузки |
| `status` | `ProcessingStatus` | Статус обработки в ETL-пайплайне |

### `RawDataItem`

Один элемент данных внутри выгрузки — элемент массива `items`.

| Поле | Тип | Описание |
|------|-----|----------|
| `url` | `str` | URL конкретного элемента |
| `title` | `str` | Заголовок элемента |
| `text` | `str` | Полный текст или HTML-код элемента |
| `published_at` | `str \| None` | Сырая дата строкой (BP-2 парсит в `date`) |
| `region` | `str \| None` | Сырое имя региона (не id) |
| `media_name` | `str \| None` | Имя публикатора: у hh пусто, у новостей — СМИ |
| `extra` | `dict` | Источник-специфичные сырые факты; `{}` если их нет. У hh здесь зарплата — нормализуется в `extra.salary_from`/`salary_to`/`currency` |

### `ProcessingStatus`

| Значение | Описание |
|----------|----------|
| `PENDING` | Выгрузка создана, обработка не начата |
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
│   ├── models.py            # Pydantic модели (RawDataFile, MetaInfo, RawDataItem)
│   └── exceptions.py        # StorageError, NotFoundError, ValidationError
├── backends/
│   └── disk_backend.py      # DiskBackend: JSONB на диске (async, aiofiles)
├── services/
│   └── repository.py        # RawDataRepository
└── utils/
    ├── hashing.py           # compute_sha256()
    └── path_generator.py    # PathGenerator (YYYY/MM/DD/trigger_{id}/raw_{id}.json)
```

## Хранение

### DiskBackend

Данные сохраняются в JSONB-файлы с иерархической структурой каталогов:

```
data/raw/
└── 2026/
    └── 07/
        └── 20/
            └── trigger_6318034066/
                └── raw_a1b2c3d4-....json
```

Структура JSONB-файла:

```json
{
  "meta": {
    "search_task_id": 1,
    "source": "fedresurs.ru",
    "competitor": "ООО СИТИГРАД",
    "trigger": "6318034066",
    "source_request_url": "https://fedresurs.ru/company/...",
    "fetched_at": "2026-07-25T23:42:59+05:00",
    "status": "pending"
  },
  "items": [
    {
      "url": "https://fedresurs.ru/sfactmessages/...",
      "title": "Недостоверность сведений",
      "text": "<!DOCTYPE html><html>...</html>",
      "published_at": "07.07.2026",
      "region": null,
      "media_name": null,
      "extra": {}
    }
  ]
}
```

Текстовые данные (HTML) сохраняются как строки UTF-8. Бинарные данные (PDF, изображения) не поддерживаются в текущей версии — для них требуется отдельный бэкенд.

## Дедупликация

Модуль поддерживает дедупликацию через внедряемый `BaseDeduplicator`. По умолчанию используется `ContentHashDeduplicator` — дедупликация по **хэшу содержимого `items`** (`utils/hashing.py::compute_items_hash`), а не по `raw_id`.

Почему не по `raw_id`: `RawDataFile.raw_id` получает свежий случайный UUID при каждом конструировании (`core/models.py`, `default_factory=uuid4`), поэтому совпадение по нему практически никогда не происходит — проверка была бы бесполезной. Реальный смысл имеет дубликат по содержимому: та же выгрузка сохраняется повторно (например, при ретрае).

```python
# Поведение по умолчанию: повторное сохранение того же содержимого
# не создаёт вторую запись, а возвращает путь к уже существующей.
repo = RawDataRepository(storage_backend=backend)
path_a = await repo.save(batch)
path_b = await repo.save(batch)  # тот же набор items
assert path_a == path_b
```

Своя стратегия дедупликации подключается через параметр `deduplicator`:

```python
from src.bp1.raw_storage.core.interfaces import (
    BaseDeduplicator,
    NoOpDeduplicator,
)


class MyDeduplicator(BaseDeduplicator):
    async def is_duplicate(self, identifier: str) -> bool:
        # identifier — хэш содержимого items
        ...


repo = RawDataRepository(
    storage_backend=backend,
    deduplicator=MyDeduplicator(),
)

# Явно отключить дедупликацию (каждое сохранение создаёт новый файл):
repo = RawDataRepository(
    storage_backend=backend,
    deduplicator=NoOpDeduplicator(),
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
