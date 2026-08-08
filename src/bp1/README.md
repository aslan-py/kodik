# BP-1: Сбор данных (Bronze Layer)

BP-1 — первый слой ETL-пайплайна системы конкурентной разведки. Отвечает за сбор сырых данных из внешних источников (федеральные реестры, API, сайты) и сохранение их в структурированном виде для последующей обработки в BP-2 (Silver Layer).

## Статус: ✅ РАБОТАЕТ

- **fedresurs.ru** — полностью реализован RPA-парсер с обходом QRATOR антибот-защиты
- **Остальные источники** — адаптеры-заглушки (интеграция готова, логика парсинга в разработке)
- **Raw Storage** — модуль хранения сырых данных (Bronze Layer) реализован и протестирован
- **CI/CD** — 100% тестов проходят (pytest), линтер (ruff) чист

## Архитектура

```
src/bp1/
├── __init__.py              # Публичный API, реэкспорт моделей и парсеров
├── base_parser.py           # Базовый класс парсера + ParserFactory
├── models.py                # SQLAlchemy модели (Trigger, Competitor, Source, SearchTask, RawItem)
├── constants.py             # Константы (таймауты, статусы, режимы запуска)
├── runner.py                # Оркестратор BPRunner (direct / celery режимы)
├── tasks.py                 # Основная логика: run_parser_async, хэширование, сохранение
├── celery_tasks.py          # Celery-обёртка для production-запуска
├── cli.py                   # CLI-интерфейс (запуск, список задач, очистка Redis)
├── test_parser.py           # Интеграционный тест с реальной БД и Redis
│
├── parsers/                 # Адаптеры парсеров (реализуют BaseParser)
│   ├── __init__.py          # Регистрация всех адаптеров в ParserFactory
│   ├── fedresurs_adapter.py # ✅ fedresurs.ru (RPA, QRATOR bypass)
│   ├── kad_arbitr_adapter.py# ⏳ kad.arbitr.ru (заглушка)
│   ├── hh_adapter.py        # ⏳ hh.ru (заглушка)
│   ├── fips_adapter.py      # ⏳ fips.ru (заглушка)
│   ├── google_news_adapter.py# ⏳ Google News (заглушка)
│   ├── kodik_forum_adapter.py# ⏳ kodik.ru/forum (заглушка)
│   ├── nic_ru_adapter.py    # ⏳ nic.ru (заглушка)
│   ├── vk_adapter.py        # ⏳ VK API (заглушка)
│   └── zakupki_adapter.py   # ⏳ zakupki.gov.ru (заглушка)
│
├── collectors/              # Движки парсинга (реализация сбора данных)
│   ├── fedresurs_rpa/       # ✅ RPA-парсер fedresurs.ru
│   ├── kad_arbitr_rpa/      # 🚧 RPA-парсер kad.arbitr.ru (в разработке)
│   ├── stealth/             # ✅ Модуль антиобнаружения (QRATOR bypass, JS evasions)
│   ├── hh_api/              # 🚧 API-парсер hh.ru
│   ├── fips_rpa/            # 🚧 RPA-парсер fips.ru
│   ├── google_news_rpa/     # 🚧 RPA-парсер Google News
│   ├── kodik_forum_rpa/     # 🚧 RPA-парсер kodik.ru/forum
│   ├── nic_ru_rpa/          # 🚧 RPA-парсер nic.ru
│   ├── vk_api/              # 🚧 API-парсер VK
│   └── zakupki_rpa/         # 🚧 RPA-парсер zakupki.gov.ru
│
└── raw_storage/             # ✅ Модуль хранения сырых данных (Bronze Layer)
    ├── core/models.py       # Pydantic модели (RawDataFile, MetaInfo, RawDataItem)
    ├── core/interfaces.py   # Абстрактные интерфейсы (BaseStorage, BaseDeduplicator)
    ├── backends/disk_backend.py  # DiskBackend — JSONB на диске
    ├── services/repository.py    # RawDataRepository
    └── utils/               # Хэширование, генерация путей
```

## Модели данных

### Справочники (конфигурация)

| Модель | Назначение | Ключевые поля |
|--------|-----------|---------------|
| [`Trigger`](src/bp1/models.py:40) | Ключевые слова для поиска | `keyword` (уникальный) |
| [`Competitor`](src/bp1/models.py:64) | Конкуренты для мониторинга | `name`, `inn` (опционально) |
| [`Source`](src/bp1/models.py:90) | Источники данных | `name` (уникальный) |
| [`SearchTask`](src/bp1/models.py:108) | Матрица конфигурации | `competitor_id`, `source_id`, `trigger_id` |

### Хранилище результатов

| Модель | Назначение | Ключевые поля |
|--------|-----------|---------------|
| [`RawItem`](src/bp1/models.py:173) | Сырые результаты парсинга | `search_task_id`, `status`, `content_hash`, `raw_data` (JSONB), `html_file_path` |

**Жизненный цикл RawItem:**
1. `new` — данные впервые собраны
2. `changed` — данные изменились (новый хэш)
3. `error` — ошибка сбора (с пустым контентом и `error_message`)
4. При совпадении хэша — строка НЕ создаётся, обновляется только `updated_at`

## Поток выполнения

```
SearchTask (БД)
    │
    ▼
BPRunner / Celery
    │
    ├─ 1. Получить конфигурацию задачи (competitor, source, trigger)
    ├─ 2. Создать парсер через ParserFactory
    ├─ 3. Выполнить парсинг (BaseParser.parse())
    ├─ 4. Вычислить хэш содержимого (MD5 от items)
    ├─ 5. Сверить с Redis (предыдущий хэш)
    │
    ├── [хэш совпал] → обновить updated_at → статус "unchanged"
    │
    └── [хэш новый] → сохранить HTML + JSON → записать RawItem → обновить Redis
```

## Режимы запуска

### Direct (тестовый)

Прямой запуск без Celery, для отладки и разработки:

```bash
# Все активные задачи
python -m src.bp1.cli run --mode direct

# Конкретная задача
python -m src.bp1.cli run --task-id 26 --mode direct

# Несколько задач
python -m src.bp1.cli run --task-ids 1,2,3 --mode direct

# С видимым браузером (для отладки)
python -m src.bp1.cli run --task-id 26 --mode direct --no-headless
```

### Celery (production)

Запуск через Celery-воркеры:

```bash
# Отправить задачи в очередь
python -m src.bp1.cli run --mode celery

# Запустить воркер
celery -A core.celery_app worker --loglevel=info
```

### Вспомогательные команды

```bash
# Список активных задач
python -m src.bp1.cli list

# Очистить Redis от ключей задач
python -m src.bp1.cli clear-redis
```

## Программный запуск

```python
import asyncio
from src.bp1 import run_pipeline, RunMode

# Асинхронный запуск
results = asyncio.run(
    run_pipeline(
        mode=RunMode.DIRECT,
        task_ids=[26],          # None = все активные
        headless=True,
        timeout=60000,
    )
)

# Синхронная обёртка
from src.bp1 import run_pipeline_sync
results = run_pipeline_sync(mode=RunMode.DIRECT)
```

## Парсеры

### Единый контракт

Все парсеры реализуют [`BaseParser`](src/bp1/base_parser.py:114):

```python
class BaseParser(ABC):
    async def parse(self, url: str, **kwargs) -> ParsedResponse: ...
    def get_source_name(self) -> str: ...
    def get_parser_type(self) -> str: ...  # 'api' или 'rpa'
```

### Выходной формат

```python
class ParsedResponse(BaseModel):
    meta: dict      # search_task_id, source, competitor, trigger, fetched_at
    items: list[ParsedItem]  # массив результатов

class ParsedItem(BaseModel):
    url: str              # ссылка на событие
    title: str            # заголовок
    text: str | None      # тело/описание
    published_at: str | None  # сырая дата
    region: str | None    # регион
    media_name: str | None    # СМИ/публикатор
    extra: dict           # источник-специфичные поля
```

### ✅ FedresursAdapter (fedresurs.ru)

Единственный полностью реализованный парсер. Использует RPA (Playwright) с обходом QRATOR антибот-защиты.

**Возможности:**
- Поиск компании по ИНН на fedresurs.ru
- Обход QRATOR anti-bot (JS challenge → cookie → навигация)
- Антидетект-стелс (JS evasions: webdriver, chrome, plugins, navigator, WebGL)
- Пул User-Agent'ов (5 вариантов Chrome)
- Извлечение структурированных данных: статус, дата регистрации, регион, руководитель
- Сохранение отрендеренного HTML (Angular SPA)
- Retry-логика (3 попытки с exponential backoff)
- Поддержка прокси

**Использование:**
```python
from src.bp1.parsers import FedresursAdapter

parser = FedresursAdapter(headless=True)
result = await parser.parse(
    url="https://fedresurs.ru",
    inn="7712345678",
    name='ООО "Ромашка"',
    search_task_id=1,
)
```

### ⏳ Адаптеры-заглушки

Остальные адаптеры зарегистрированы в [`ParserFactory`](src/bp1/parsers/__init__.py:18) и готовы к интеграции, но возвращают заглушечные данные:

| Адаптер | Источник | Тип | Статус |
|---------|----------|-----|--------|
| `FedresursAdapter` | fedresurs.ru | RPA | ✅ |
| `KadArbitrAdapter` | kad.arbitr.ru | RPA | ⏳ заглушка |
| `HHAdapter` | api.hh.ru | API | ⏳ заглушка |
| `FipsAdapter` | fips.ru | RPA | ⏳ заглушка |
| `GoogleNewsAdapter` | news.google.com | RPA | ⏳ заглушка |
| `KodikForumAdapter` | kodik.ru/forum | RPA | ⏳ заглушка |
| `NicRuAdapter` | nic.ru | RPA | ⏳ заглушка |
| `VKAdapter` | dev.vk.com | API | ⏳ заглушка |
| `ZakupkiAdapter` | zakupki.gov.ru | RPA | ⏳ заглушка |

## Stealth — модуль антиобнаружения

Переиспользуемый модуль для обхода антибот-систем. Подробнее в [stealth/README.md](src/bp1/collectors/stealth/README.md).

**Ключевые возможности:**
- [`apply_stealth()`](src/bp1/collectors/stealth/browser_config.py) — инъекция JS-обманок (5 секций: webdriver, chrome, plugins, navigator, webgl)
- [`bypass_qrator()`](src/bp1/collectors/stealth/qrator_bypass.py) — обход QRATOR (25с ожидание JS challenge + двухшаговая навигация)
- [`get_launch_args()`](src/bp1/collectors/stealth/browser_config.py) — anti-detection аргументы Chromium
- [`get_context_config()`](src/bp1/collectors/stealth/browser_config.py) — настройки контекста (locale, timezone, viewport)

## Raw Storage — Bronze Layer

Модуль хранения сырых данных в JSONB-формате. Подробнее в [raw_storage/README.md](src/bp1/raw_storage/README.md).

**Структура JSONB-файла:**
```json
{
  "meta": {
    "search_task_id": 1,
    "source": "fedresurs.ru",
    "competitor": "ООО СИТИГРАД",
    "trigger": "6318034066",
    "source_request_url": "https://fedresurs.ru/...",
    "fetched_at": "2026-07-25T23:42:59+05:00",
    "status": "pending"
  },
  "items": [
    {
      "url": "https://fedresurs.ru/company/...",
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

## Хэширование и дедупликация

BP-1 использует двухуровневую систему дедупликации:

1. **Redis** — хранит последний хэш для каждой `search_task_id`. При совпадении хэша строка RawItem не создаётся.
2. **MD5 от items** — хэш считается только от содержимого `items` (без `meta` и `file_path`), что позволяет детектировать смысловые изменения данных.

## Тестирование

### Модульные тесты

```bash
# Все тесты BP-1
pytest kodik/tests/bp1/ -v

# Только fedresurs
pytest kodik/tests/bp1/fedresurs/ -v

# С coverage
pytest kodik/tests/bp1/ --cov=src.bp1 -v
```

### Покрытие тестами (fedresurs)

| Модуль | Файл тестов | Что тестируется |
|--------|-------------|-----------------|
| `browser.py` | [`test_browser.py`](kodik/tests/bp1/fedresurs/test_browser.py) | BrowserManager, _build_proxy_dict |
| `parser.py` | [`test_parser.py`](kodik/tests/bp1/fedresurs/test_parser.py) | FedresursRPA, retry-логика, _execute_search |
| `extractor.py` | [`test_extractor.py`](kodik/tests/bp1/fedresurs/test_extractor.py) | CompanyDataExtractor, _parse_raw_text |
| `constants.py` | [`test_constants.py`](kodik/tests/bp1/fedresurs/test_constants.py) | Константы, SELECTORS, UA, задержки |
| `schemas.py` | [`test_schemas.py`](kodik/tests/bp1/fedresurs/test_schemas.py) | SearchRequest, SearchResult, ProxyConfig |
| `utils.py` | [`test_utils.py`](kodik/tests/bp1/fedresurs/test_utils.py) | validate_inn, format_proxy_string, generate_filename |
| `exceptions.py` | [`test_exceptions.py`](kodik/tests/bp1/fedresurs/test_exceptions.py) | Иерархия исключений |

### Интеграционный тест

```bash
# Требует: PostgreSQL + Redis + активные search_task в БД
python -m src.bp1.test_parser
```

Тест использует реальную БД и Redis, выполняет все активные задачи и выводит детальный отчёт.

## Настройка

### Переменные окружения (`.env`)

```ini
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/kodik

# Redis
REDIS_URL=redis://localhost:6379/0

# Директории для хранения данных
BP1_HTML_DIR=src/bp1/data/html_pages
BP1_RAW_DIR=src/bp1/data/raw
```

### Инициализация данных

```bash
# Создать справочники (competitor, source, trigger)
python -m core.scripts.stages.dictionaries

# Создать search_task (матрица конфигурации)
python -m core.scripts.stages.bp1
```

## Зависимости

- **Python 3.12+**
- **PostgreSQL 15+** (asyncpg)
- **Redis 7+**
- **Playwright** (Chromium) — для RPA-парсеров
- **Celery** — для production-режима
- **Pydantic 2.x** — модели данных
- **SQLAlchemy 2.x** (asyncio) — ORM
- **aiofiles** — асинхронная работа с файлами

## План развития

- [ ] Реализовать RPA-парсер для kad.arbitr.ru (в процессе)
- [ ] Реализовать API-парсер для hh.ru
- [ ] Реализовать RPA-парсер для fips.ru
- [ ] Реализовать парсер для Google News
- [ ] Реализовать парсер для VK API
- [ ] Реализовать S3-бэкенд для raw_storage
- [ ] Добавить интеграционные тесты для всех адаптеров
