# BP-1: Сбор данных (Bronze Layer)

BP-1 — первый слой ETL-пайплайна системы конкурентной разведки. Отвечает за сбор сырых данных из внешних источников (федеральные реестры, API, сайты) и сохранение их в структурированном виде для последующей обработки в BP-2 (Silver Layer).

## Статус: ✅ РАБОТАЕТ

- **fedresurs.ru** — полностью реализован RPA-парсер с обходом QRATOR антибот-защиты
- **Адаптивный движок (adaptive)** — полностью реализован: автоматическая классификация источников, иерархия стратегий обхода с деградацией (FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL), интеллектуальное извлечение через LLM, кэширование адаптеров и CLI
- **Остальные источники** — обрабатываются универсальным `AdaptiveBridgeParser` (авто-детекция структуры сайта без ручной настройки)
- **Адаптивный поиск (Adaptive Search)** — полностью реализован: source-aware выбор поискового параметра (ИНН для гос. источников, название конкурента для остальных), per-source шаблоны URL поиска (например, `hh.ru → /search/vacancy?text=`), пропуск задач по `is_active`, circuit breaker (авто-блокировка источника при сбоях)
- **Задания для планировщика (`jobs.py`)** — четыре самодостаточных задания (`collect_source`, `collect_competitor`, `collect_all`, `register_source`) с контрактом «только примитивы на входе / JSON-сериализуемый результат / идемпотентность», спроектированы так, чтобы оборачиваться в Celery task и Celery beat без адаптеров (см. [«Подключение к Celery: tasks и beat»](#подключение-к-celery-tasks-и-beat))
- **Контракт `raw_data` (`meta`/`metrics`)** — метаданные выгрузки (`ParsedMeta`) и диагностика прогона (`ParsedMetrics`) разделены и закреплены тестом-контрактом против `ABOUT_PROJECT/ABOUT.md`, чтобы не расходиться незаметно (см. [«Выходной формат»](#выходной-формат))
- **Raw Storage** — модуль хранения сырых данных (Bronze Layer) реализован и протестирован
- **CI/CD** — 100% тестов проходят (pytest), линтер (ruff) чист

## Архитектура

```
src/bp1/
├── __init__.py              # Публичный API, реэкспорт моделей и парсеров
├── base_parser.py           # Базовый класс парсера + ParserFactory + ParsedItem/ParsedResponse
├── models.py                # SQLAlchemy модели (Trigger, Competitor, Source, SearchTask, RawItem)
├── constants.py             # Константы (таймауты, статусы, режимы запуска)
├── storage.py               # ✅ RawDataService — единая персистентность (хэш, Redis, HTML/JSON, RawItem)
├── runner.py                # Оркестратор BPRunner (direct / celery режимы)
├── tasks.py                 # Основная логика: run_parser_async, получение конфигурации задачи
├── celery_tasks.py          # Celery-обёртка для run_parser_async (низкий уровень, по task_id)
├── cli.py                   # Единый CLI этапа (source/competitor/all/add-source)
├── jobs.py                  # ✅ Задания сбора: collect_source/collect_competitor/collect_all/
│                            #    register_source — публичный API для CLI, Celery task и beat
├── pipeline.py              # run_bp1() — точка входа этапа 1 + сводка прогона
│
├── parsers/                 # Адаптеры парсеров (реализуют BaseParser)
│   ├── __init__.py          # Регистрация адаптеров в ParserFactory
│   ├── fedresurs_adapter.py # ✅ fedresurs.ru (RPA, QRATOR bypass)
│   └── ...                  # Остальные источники — через универсальный AdaptiveBridgeParser
│
├── adaptive/                # ✅ Адаптивный сбор данных (интеллектуальный парсинг)
│   ├── schemas.py           # Pydantic-схемы (классификация, стратегии, HITL, отчёты)
│   ├── hostname.py          # Общая нормализация hostname + список гос. доменов
│   ├── core/                # UnifiedCache (Redis+диск), DataQualityGate (5 уровней)
│   ├── processing/          # AdaptiveParser, HtmlCleaner, StructuredChunker, ResultMerger
│   │   └── _llm/            # Промпты, схемы ответов, мапперы, эвристики, клиент
│   ├── strategies/          # SourceClassifier, AgenticOrchestrator, Crawl4AI/Stealth/HITL, engines
│   └── integration/         # AdaptiveBridgeParser, AdaptiveRunner, SourceRegistrationService,
│                            # SearchUrlProber (перебор параметров / POST-форма / переформулировки)
│
├── collectors/              # Движки парсинга (реализация сбора данных)
│   ├── fedresurs_rpa/       # ✅ RPA-парсер fedresurs.ru
│   └── stealth/             # ✅ Модуль антиобнаружения (QRATOR bypass, JS evasions)
│
└── raw_storage/             # ✅ Модуль хранения сырых данных (Bronze Layer)
    ├── core/models.py       # Pydantic модели (RawDataFile, MetaInfo, RawDataItem)
    ├── core/interfaces.py   # Абстрактные интерфейсы (BaseStorage, BaseDeduplicator)
    ├── core/deduplication.py # ContentHashDeduplicator — дедуп по хэшу содержимого
    ├── backends/disk_backend.py  # DiskBackend — JSONB на диске
    ├── services/repository.py    # RawDataRepository (CRUD + дедупликация)
    ├── factory.py           # StorageFactory — фабрика бэкендов
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
Активные Competitor × Source (БД)
    │
    ├─ sync_search_task_coverage → недостающие SearchTask без trigger
    │
    ▼
BPRunner / AdaptiveRunner / Celery
    │
    ├─ 1. Получить конфигурацию задачи (competitor, source, trigger, is_active)
    ├─ 2. Создать парсер через ParserFactory / SourceClassifier
    ├─ 3. Выполнить парсинг (BaseParser.parse() или адаптивный парсинг)
    ├─ 4. Вычислить хэш содержимого (MD5 от items)
    ├─ 5. Сверить с Redis (предыдущий хэш)
    │
    ├── [хэш совпал] → обновить updated_at → статус "unchanged"
    │
    └── [хэш новый] → сохранить HTML + JSON → записать RawItem → обновить Redis
```

## Режимы запуска

### Через реестр конвейера (рекомендуемый способ)

`src/bp1/pipeline.py::run_bp1()` — точка входа этапа 1 конвейера, по
тому же контракту, что `run_bp2`…`run_bp7`: без аргументов, сама
открывает сессию БД и Redis-клиент, досоздаёт в той же транзакции задачи
без поискового слова для всех активных пар «конкурент × источник», вызывает
`AdaptiveRunner.run_all()` и сворачивает результат в сводку прогона. Поле
`search_tasks_created` показывает число созданных в этом прогоне задач.
Через неё этап 1 запускается кнопкой в админке,
`core/pipeline/cli.py` и по расписанию Celery — как и остальные шесть
этапов (см. `core/pipeline/registry.py`).

```bash
python -m core.pipeline.cli 1          # этап 1 (реализация — по TRUE_PARSING)
python -m core.pipeline.cli 1 real     # разово настоящий сбор
python -m core.pipeline.cli 1 stub     # разово заглушка
python -m core.pipeline.cli all        # весь конвейер 1..7
python -m src.bp1.search_task_coverage # только создать задачи, без сбора
```

Синхронизация только добавляет отсутствующие задачи с пустым `trigger_id`.
Она не удаляет строки, не меняет `is_active` и не трогает ручные задачи с
поисковым словом. Чтобы исключить отдельную пару из сбора, деактивируйте её
задачу: удалённая строка будет создана заново при следующем запуске.

Так замыкается расширение источников: BP-3 находит кандидата, BP-7 переносит
подходящий домен в `source`, а ближайший реальный прогон BP-1 автоматически
создаёт по нему задачи для всех активных конкурентов и начинает сбор.

Рядом с этой точкой входа у этапа 1 есть вторая реализация — заглушка
(`core/scripts/stages/bp1_stub.py`, шесть синтетических новостей, без
сети и LLM), нужная для дешёвой сквозной проверки этапов 2-7. Какая из
двух выполняется по умолчанию — решает настройка `TRUE_PARSING` в
`.env` (см. `core/scripts/SCRIPTS_README.md`, «Три способа наполнить
этап 1»); режимы ниже (Direct/Celery/адаптивный CLI) — более низкий
уровень, `run_bp1()` их не заменяет, а вызывает `AdaptiveRunner` тем же
способом, что и команда `all` объединённого CLI.

### CLI этапа

Единая точка входа — `python -m src.bp1.cli`. Прежние два интерфейса
(`src/bp1/cli.py` с `run --mode direct|celery` и `src/bp1/adaptive/cli.py`)
объединены: рабочие сценарии были размазаны по двум командам с разными
флагами для одного и того же.

Четыре команды сбора — тонкие обёртки над заданиями
[`src/bp1/jobs.py`](src/bp1/jobs.py); вся логика живёт там, поэтому
планировщик задач вызывает те же функции напрямую, без CLI.

```bash
# 1. Один источник по всем активным конкурентам
python -m src.bp1.cli source lenta.ru

# 2. Один конкурент по всем активным источникам
#    (конкурента, которого нет в БД, задание создаёт само)
python -m src.bp1.cli competitor "Сбербанк"
python -m src.bp1.cli competitor "Сбербанк" --inn 7707083893

# 3. Полный прогон: все источники x все конкуренты
python -m src.bp1.cli all
python -m src.bp1.cli all --no-ensure-matrix   # только заведённые связки

# 4. Поставить новый источник на учёт (категоризация + БД + кэш)
python -m src.bp1.cli add-source https://www.lenta.ru/news
```

Общие флаги команд сбора: `--no-headless` (показать окно браузера),
`--timeout` (мс), `--max-concurrent` (параллельных задач). По умолчанию
значения берутся из настроек.

### Вспомогательные команды

```bash
# Активные связки источник-конкурент
python -m src.bp1.cli list

# Категоризация источника без записи в БД
python -m src.bp1.cli classify lenta.ru

# Кэш адаптера источника (в любой форме записи источника)
python -m src.bp1.cli cache --show lenta.ru
python -m src.bp1.cli cache --clear lenta.ru

# Последний собранный RawItem по задаче
python -m src.bp1.cli quality --task-id 26

# Сброс ключей дедупликации BP-1 в Redis
python -m src.bp1.cli clear-redis
```

## Программный запуск

```python
import asyncio
from src.bp1 import run_pipeline, RunMode

# Асинхронный запуск (direct — классический BP-1 пайплайн)
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

### Программный запуск AdaptiveRunner

```python
import asyncio
from core.database import AsyncSessionLocal
from core.redis_client import get_redis
from src.bp1.adaptive import AdaptiveRunner

async def main():
    redis = await get_redis()
    async with AsyncSessionLocal() as session:
        runner = AdaptiveRunner(
            mode='adaptive',        # 'adaptive' | 'hybrid' | 'fallback'
            headless=True,
            timeout=60000,
        )
        # 1) Одна задача по ID
        result = await runner.run_task(task_id=26, session=session, redis_client=redis)
        print(result['status'], result.get('strategy'))

        # 2) Все активные задачи (учитывает is_active для SearchTask/Source/Competitor)
        results = await runner.run_all(session, redis_client=redis)
        for r in results:
            print(r['status'], r['search_task_id'])

        # 3) Сбор по конкретной паре источник + конкурент
        res = await runner.run_source_competitor(
            source='lenta.ru',
            competitor='ООО АРХИТЕХ ИИ',
            session=session,
            redis_client=redis,
        )
        print(res['status'])
    await redis.aclose()

asyncio.run(main())
```

## Подключение к Celery: tasks и beat

Планировщик задач должен опираться на [`src/bp1/jobs.py`](src/bp1/jobs.py),
а не напрямую на `BPRunner`/`AdaptiveRunner`. Это отдельный, специально
спроектированный для очереди слой — тонкий над `AdaptiveRunner`, но с
контрактом, который переживает сериализацию брокером:

- **только примитивы на входе** (`str`/`int`/`bool`/`None`) — сессии,
  Redis-клиенты и ORM-модели наружу не выносятся;
- **самодостаточность** — каждое задание само открывает сессию БД и Redis
  и закрывает их в `finally`; обёртке не нужно готовить контекст;
- **JSON-сериализуемый результат** — обычный `dict` без Pydantic-моделей и
  `datetime`, годится как return value Celery-задачи;
- **идемпотентность** — источники, конкуренты и связки `SearchTask`
  создаются по принципу «найти или создать», поэтому повторный запуск
  (в том числе после ретрая Celery) не плодит дубли;
- **async** — в синхронном Celery-воркере оборачивается `asyncio.run(...)`.

Четыре задания: [`collect_source()`](src/bp1/jobs.py), `collect_competitor()`,
`collect_all()`, `register_source()` — см. сигнатуры и докстринги в
`jobs.py`; это те же операции, что стоят за командами CLI `source` /
`competitor` / `all` / `add-source`.

### 1. Обёртка над `app.task`

`celery_tasks.py` уже даёт готовый пример обёртки (для низкоуровневого
`run_parser_async` по одному `task_id`); для заданий планировщика паттерн
тот же — задача просто зовёт `asyncio.run()` над функцией из `jobs.py`:

```python
# src/bp1/celery_tasks.py (дополнение к существующей run_parser_task)
import asyncio

from core.celery_app import (
    CELERY_DEFAULT_RETRY_DELAY,
    CELERY_MAX_RETRIES,
    CELERY_RETRY_BACKOFF_MAX,
    app,
)
from src.bp1 import jobs


@app.task(
    bind=True,
    max_retries=CELERY_MAX_RETRIES,
    default_retry_delay=CELERY_DEFAULT_RETRY_DELAY,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=CELERY_RETRY_BACKOFF_MAX,
    retry_jitter=True,
)
def collect_all_task(self, headless: bool = True) -> dict:
    """Полный прогон: все активные источники x все активные конкуренты."""
    return asyncio.run(jobs.collect_all(headless=headless))


@app.task(bind=True, autoretry_for=(Exception,))
def collect_source_task(self, source: str, headless: bool = True) -> dict:
    """Один источник по всем активным конкурентам."""
    return asyncio.run(jobs.collect_source(source, headless=headless))


@app.task(bind=True, autoretry_for=(Exception,))
def collect_competitor_task(
    self, competitor: str, inn: str | None = None
) -> dict:
    """Один конкурент по всем активным источникам."""
    return asyncio.run(jobs.collect_competitor(competitor, inn=inn))
```

Задание — обычный `dict`, поэтому результат читается стандартно:

```python
result = collect_all_task.delay(headless=True)
result.get(timeout=600)   # -> {'job': 'collect_all', 'status': 'ok', 'success_rate': 0.86, ...}
```

### 2. Регистрация модуля в едином Celery-приложении

`core/celery_app.py` — одно Celery-приложение на весь проект; модули с
задачами регистрируются явно в `include` (автообнаружение по конвенции
`<пакет>.tasks` не используется — у BP-1 модуль называется
`celery_tasks.py`). Сейчас строка для BP-1 закомментирована — раскомментировать
её и есть акт «подключения» пакета к воркеру:

```python
# core/celery_app.py
app = Celery(
    'kodik',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend_url,
    include=[
        'src.bp1.celery_tasks',   # было закомментировано — раскомментировать
    ],
)
```

Без этой строки процесс воркера не импортирует модуль с задачами: `.delay()`
из другого процесса отправит сообщение в очередь, но обработать его будет
некому (задача останется `PENDING` навсегда).

Запуск воркера:

```bash
celery -A core.celery_app worker --loglevel=info
```

### 3. Периодический запуск через Celery Beat

`app.conf.beat_schedule` в `core/celery_app.py` заведён пустым намеренно —
структура готова принимать записи, конкретное расписание для каждого BP
оставлено на явное включение. Чтобы поставить сбор BP-1 на расписание,
добавляются записи с `crontab`:

```python
# core/celery_app.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'bp1-collect-all-nightly': {
        'task': 'src.bp1.celery_tasks.collect_all_task',
        'schedule': crontab(hour=3, minute=0),   # каждую ночь в 03:00 UTC
        'kwargs': {'headless': True},
    },
    'bp1-collect-hh-hourly': {
        'task': 'src.bp1.celery_tasks.collect_source_task',
        'schedule': crontab(minute=0),           # раз в час
        'kwargs': {'source': 'hh.ru', 'headless': True},
    },
}
```

Запуск планировщика (отдельный процесс, обычно рядом с воркером):

```bash
celery -A core.celery_app beat --loglevel=info

# или воркер + beat в одном процессе (для разработки, не для production)
celery -A core.celery_app worker -B --loglevel=info
```

Расписание в `crontab()` — по `app.conf.timezone` (`UTC`, задан в
`core/celery_app.py`). Каждая задача из `beat_schedule` обязана быть
идемпотентной и не зависеть от порядка запуска относительно других задач —
оба свойства уже обеспечены слоем `jobs.py` («найти или создать» вместо
жёсткого создания, самодостаточная сессия/Redis на задание).

## Парсеры

### Единый контракт

Все парсеры реализуют [`BaseParser`](src/bp1/base_parser.py:114):

```python
class BaseParser(ABC):
    async def parse(self, url: str, **kwargs) -> ParsedResponse: ...
    def get_source_name(self) -> str: ...
    def get_parser_type(self) -> str: ...  # 'api' | 'rpa' | 'adaptive'
    def get_parser_info(self) -> dict: ... # source, type, class
```

**Ключевые атрибуты/методы:**
- `required_kwargs` — кортеж обязательных kwargs для `parse()`. Позволяет провалидировать предусловия до запуска браузера (например, `FedresursAdapter.required_kwargs = ('inn',)` — без ИНН RPA-сценарий не запускается).
- `get_parser_info()` — возвращает `{source, type, class}`.

### Выходной формат

`meta`/`items` — бизнес-контракт, закреплённый `ABOUT_PROJECT/ABOUT.md` и
проверяемый тестом-контрактом
([`test_raw_data_contract.py`](kodik/tests/bp1/test_raw_data_contract.py));
`metrics` — диагностика конкретного прогона (сработавшая стратегия, статус
Quality Gate и т.п.), в persisted `raw_data` **не попадает**
(`exclude=True` в модели), доступна только в памяти вызывающему коду.

```python
class ParsedMeta(BaseModel):        # persisted: raw_data.meta, extra='forbid'
    search_task_id: int | None
    source: str
    competitor: str
    trigger: str | None
    source_request_url: str
    fetched_at: str

class ParsedItem(BaseModel):        # persisted: raw_data.items[], extra='forbid'
    url: str              # ссылка на событие (обязательна)
    title: str            # заголовок (обязателен)
    text: str | None      # тело/описание
    published_at: str | None  # сырая дата
    region: str | None    # регион
    media_name: str | None    # СМИ/публикатор
    extra: dict           # источник-специфичные поля (ИНН, статус, файл и др.)

class ParsedMetrics(BaseModel):     # НЕ persisted, extra='allow' (открытая диагностика)
    probed_url: str | None
    strategy_used: str | None
    quality_status: str | None
    quality_levels: dict[str, Any] | None
    relevance_mode: str | None
    news_total: int | None
    relevance_filtered: int | None
    file_saved: bool | None

class ParsedResponse(BaseModel):
    meta: ParsedMeta
    items: list[ParsedItem]
    metrics: ParsedMetrics = Field(default_factory=ParsedMetrics, exclude=True)
```

`RawDataService.persist()` (`storage.py`) сохраняет ровно
`response.model_dump()`, поэтому `metrics` физически не может попасть в БД
или на диск — единственный путь избежать повторения инцидента, когда
адаптивный мост когда-то дописывал служебные поля прямо в `meta`
(разбор — в `REFACTORING_PLAN.md`).

### ✅ FedresursAdapter (fedresurs.ru)

Полностью реализованный парсер. Использует RPA (Playwright) с обходом QRATOR антибот-защиты.

**Возможности:**
- Поиск компании по ИНН на fedresurs.ru
- Обход QRATOR anti-bot (JS challenge → cookie → навигация)
- Антидетект-стелс (JS evasions: webdriver, chrome, plugins, navigator, WebGL)
- Пул User-Agent'ов (5 вариантов Chrome)
- Извлечение структурированных данных: статус, дата регистрации, регион, руководитель
- Сохранение отрендеренного HTML (Angular SPA)
- Retry-логика (3 попытки с exponential backoff)
- Поддержка прокси — адрес автоматически подбирается из общего пула
  `src/bp1/network/pool.py` при вызове через `AdaptiveRunner`
  (`_get_parser_for_source`); при прямом вызове `FedresursAdapter`
  передаётся явно через `proxy=ProxyConfig(...)`

**Использование:**
```python
from src.bp1.parsers import FedresursAdapter

parser = FedresursAdapter(headless=True, timeout=60000)
result = await parser.parse(
    url="https://fedresurs.ru",
    inn="7712345678",
    name='ООО "Ромашка"',
    search_task_id=1,
    competitor='ООО "Ромашка"',
)
```

### ✅ AdaptiveBridgeParser (универсальный)

Мост между адаптивной подсистемой и `BaseParser`. Автоматически классифицирует источник, выбирает стратегию и извлекает данные без ручной настройки.

```python
from src.bp1.adaptive import AdaptiveBridgeParser

parser = AdaptiveBridgeParser(headless=True, timeout=60000)
response = await parser.parse(
    "https://lenta.ru/",
    source_name="lenta.ru",     # реальное имя источника для кэша классификации
    search_task_id=1,
    competitor="ООО АРХИТЕХ ИИ",
    trigger="Архитектура",
)
```

## Adaptive — адаптивный сбор данных

Подробное описание в [adaptive/README.md](src/bp1/adaptive/README.md).

### Ключевые возможности

- **Классификация источников** — [`SourceClassifier`](src/bp1/adaptive/strategies/classifier.py:168) определяет тип сайта (новостной, реестр, API, SPA), антибот-защиту (Cloudflare, DataDome, QRATOR, Akamai, Incapsula), CAPTCHA (reCAPTCHA, hCaptcha), SPA-фреймворки (React, Vue, Nuxt, Next.js, Angular) и рекомендует стратегию.
- **Классификация учится на фактах** — классификация уточняется по РЕАЛЬНОМУ HTML (а не вслепую по имени источника) и переписывается по факту сработавшей стратегии: если закэшировано `FAST`, а сбор реально прошёл через `STEALTH`, кэш обновляется, и следующий прогон не проходит всю лестницу деградации заново. Флаги защиты только усиливаются (`False → True`) и не сбрасываются одним снимком HTML.
- **LLM-категоризация подключена к бою** — [`LLMClient.classify_with_llm`](src/bp1/adaptive/processing/llm.py) (промпт `SITE_CLASSIFICATION_PROMPT_V2`, 20 типов сайта) вызывается один раз на источник, когда адаптер выводится впервые. Уточняет признаки защиты там, где эвристика по ключевым словам ничего не находит; сбой LLM не ломает сбор.
- **Иерархия стратегий с деградацией** — [`AgenticOrchestrator`](src/bp1/adaptive/strategies/orchestrator.py) пробует стратегии по порядку `FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL`. При ошибке, контенте < 300 символов или «пустом JS-каркасе» (нет ссылок) переходит к следующей. **Заведомо бесполезные стратегии пропускаются**: при известной CAPTCHA — сразу `STEALTH/WAYBACK/HITL`, при антиботе без SPA — без `CRAWL4AI`.
- **Интеллектуальный парсинг** — [`AdaptiveParser`](src/bp1/adaptive/processing/parser.py) извлекает реальные CSS-селекторы и схему данных через LLM, кэширует адаптеры в Redis (TTL 7 дней).
- **Самокоррекция адаптера** — если закэшированный адаптер дважды подряд не проходит Quality Gate, он сбрасывается (селекторы выводятся заново), а у LLM запрашивается диагностическая рекомендация (`extra.adapter_review`). Успешный прогон обнуляет счётчик.
- **Чанкирование больших страниц** — `HtmlCleaner → StructuredChunker → параллельное извлечение → ResultMerger` для HTML, не помещающегося в контекст LLM.
- **5 уровней контроля качества** — [`DataQualityGate`](src/bp1/adaptive/core/quality.py): SCHEMA, TYPES, BUSINESS, VOLUME, CONSISTENCY с Quarantine-паттерном. Результаты по уровням доходят до сводки прогона.
- **HITL для CAPTCHA** — [`HITLManager`](src/bp1/adaptive/strategies/hitl.py) запускает видимый браузер, детектирует момент решения CAPTCHA и кэширует cookies в профиль.
- **Регистрация источников** — [`SourceRegistrationService`](src/bp1/adaptive/integration/sources.py) по ссылке нормализует адрес, классифицирует сайт, добавляет `Source` в БД, кэширует классификацию и (в CLI `add-source`) проверяет, отвечает ли поисковый эндпоинт.
- **Source-aware выбор поискового параметра** — для гос. источников (реестры) поиск по ИНН, для остальных — по названию конкурента.
- **Per-source шаблоны URL** — `SearchUrlTemplateRegistry` задаёт специфичные пути поиска (например, `hh.ru → /search/vacancy?text=`), с fallback на универсальный `/search?q=`.
- **Пробинг поиска** — [`SearchUrlProber`](src/bp1/adaptive/integration/search_probe.py) перебирает имена query-параметров (`q`, `query`, `text`, …), пробует POST-форму и упрощает запрос (без кавычек / без ОПФ / первое значимое слово), проверяя, есть ли цель в выдаче.
- **Параллельный сбор** — `AdaptiveRunner.run_all()` выполняет задачи одновременно (`max_concurrent`), каждая со своей сессией БД.
- **Метрики прогона** — `run_bp1()` возвращает `success_rate`, разбивку по фактически сработавшим стратегиям, по уровням Quality Gate и список источников с низким качеством; отсутствие `crawl4ai`/`playwright` фиксируется предупреждением до прогона.
- **RSS/Atom и sitemap.xml для новостных источников** — для `SourceType.NEWS` перед HTML-лестницей пробуется RSS/Atom-фид или `sitemap.xml` (дешевле, без браузера и LLM-подбора селекторов); при отсутствии/отказе — обычная HTML-лестница без изменений. Подробнее — [adaptive/README.md](src/bp1/adaptive/README.md#rssatom-и-sitemapxml-альтернатива-html-лестнице-для-новостных-источников).

### Адаптивный поиск (Adaptive Search)

Адаптивный поиск — это механизм формирования и выполнения поискового запроса
для каждого источника. Он решает три задачи: **какой параметр** передать в
поиск, **по какому URL-шаблону** искать, и **выполнять ли поиск вообще**.

#### Как выбирается поисковый параметр

[`SearchParamResolver`](src/bp1/adaptive/integration/sources.py:179) определяет,
искать по ИНН или по названию конкурента:

- **Гос. источники** (реестры: `fedresurs.ru`, `kad.arbitr.ru`, `zakupki.gov.ru`,
  `nalog.ru`, `egrul.nalog.ru`, `fips.ru`; типы `SiteType.GOVERNMENT`/`LEGAL`)
  → поиск по **ИНН**. Приоритет: `competitor_inn` → `trigger` (если это 10/12
  цифр) → название конкурента.
- **Все остальные** (новостные, job-board и т.д.) → поиск по **названию
  конкурента** (`competitor.name`), т.к. на не-госсайтах ИНН не индексируется,
  а триггер (ключевое слово) не является названием компании. Пример: поиск на
  `hh.ru` по триггеру «Москва» не находит вакансии ООО «АРХИТЕХ ИИ» — поиск
  идёт по названию компании.

#### Как формируется URL поиска

[`SearchUrlTemplateRegistry`](src/bp1/adaptive/integration/sources.py:92) выбирает
per-source шаблон пути с fallback на универсальный `/search?q=`:

```python
from src.bp1.adaptive.integration.sources import (
    SearchParamResolver,
    SearchUrlTemplateRegistry,
)

# Источник предпочитает ИНН (гос. реестр)?
resolver = SearchParamResolver()
param = resolver.resolve(
    'fedresurs.ru',
    competitor_inn='9718283930',
    competitor='ООО Кодик',
    trigger=None,
)
print(param)  # '9718283930'  — ИНН для гос. источника

# На не-гос. источнике поиск идёт по названию конкурента.
param = resolver.resolve(
    'hh.ru', competitor_inn=None, competitor='ООО АРХИТЕХ ИИ', trigger='Москва'
)
print(param)  # 'ООО АРХИТЕХ ИИ'

# Построение URL с per-source шаблоном (hh.ru → /search/vacancy?text=).
registry = SearchUrlTemplateRegistry()
print(registry.build_url('hh.ru', 'ООО АРХИТЕХ ИИ'))
```

#### Когда поиск пропускается

- **`is_active = False`** — если у `SearchTask`, `Source` или `Competitor`
  выключен флаг активности, задача пропускается, в JSON фиксируется
  `error: is_active=False`.
- **Отсутствие ИНН у гос. источника** — `SearchParamResolver.missing_inn()`
  определяет, что источнику нужен ИНН, а у конкурента его нет. Поиск не
  выполняется, в JSON пишется `error: not INN` (избегает бесполезных запросов).
- **Circuit breaker** — если источник временно заблокирован в Redis (все
  стратегии падали недавно), задача пропускается со статусом
  `source_unavailable`. После `source_disable_threshold` подряд отказов источник
  автоматически отключается в БД (`is_active=False`).

#### Использование в CLI

```bash
# Регистрация нового источника (классификация + БД + Redis) перед поиском
python -m src.bp1.cli add-source https://hh.ru

# Сбор по источнику: связки Source/Competitor/SearchTask достраиваются
# автоматически по всем активным конкурентам.
python -m src.bp1.cli source hh.ru

# Сбор по конкуренту (по всем активным источникам)
python -m src.bp1.cli competitor "ООО АРХИТЕХ ИИ"

# Все активные задачи (учитывает is_active всех трёх уровней)
python -m src.bp1.cli all
```

#### Использование в коде

```python
import asyncio
from core.database import AsyncSessionLocal
from core.redis_client import get_redis
from src.bp1.adaptive import AdaptiveRunner

async def main():
    runner = AdaptiveRunner(mode='adaptive', headless=True, timeout=60000)
    redis = await get_redis()
    try:
        async with AsyncSessionLocal() as session:
            # 1) Все активные задачи из БД (с учётом is_active).
            results = await runner.run_all(session, redis_client=redis)

            # 2) По конкретной паре источник + конкурент (создаёт задачу).
            res = await runner.run_source_competitor(
                source='hh.ru',
                competitor='ООО АРХИТЕХ ИИ',
                session=session,
                redis_client=redis,
            )
            print(res['status'], res.get('strategy'))
    finally:
        await redis.aclose()

asyncio.run(main())
```

### Адаптивный парсинг из кода

```python
import asyncio
from src.bp1.adaptive import AdaptiveParser

async def main():
    parser = AdaptiveParser(headless=True, timeout=60000)
    result = await parser.parse(
        url="https://lenta.ru/",
        source_name="lenta.ru",
        competitor="ООО АРХИТЕХ ИИ",
        trigger="Архитектура",
    )
    print(result.status, result.items, result.strategy_used)

asyncio.run(main())
```

### Регистрация собственной стратегии

```python
from src.bp1.adaptive import AgenticOrchestrator, StrategyType
from src.bp1.adaptive.strategies.orchestrator import BaseStrategy
from src.bp1.adaptive.schemas import StrategyResult

class MyStrategy(BaseStrategy):
    strategy_type = StrategyType.CRAWL4AI

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        return StrategyResult(
            strategy=self.strategy_type,
            success=True,
            data='<html>...</html>',
            content_length=1000,
        )

orch = AgenticOrchestrator()
orch.register_strategy(MyStrategy.strategy_type, MyStrategy())
```

## Stealth — модуль антиобнаружения

Переиспользуемый модуль для обхода антибот-систем. Подробнее в [stealth/README.md](src/bp1/collectors/stealth/README.md).

**Ключевые возможности:**
- [`apply_stealth()`](src/bp1/collectors/stealth/browser_config.py) — инъекция JS-обманок (5 секций: webdriver, chrome, plugins, navigator, webgl)
- [`bypass_qrator()`](src/bp1/collectors/stealth/qrator_bypass.py) — обход QRATOR (25с ожидание JS challenge + двухшаговая навигация)
- [`get_launch_args()`](src/bp1/collectors/stealth/browser_config.py) — anti-detection аргументы Chromium
- [`get_context_config()`](src/bp1/collectors/stealth/browser_config.py) — настройки контекста (locale, timezone, viewport)

## Raw Storage — Bronze Layer

Модуль хранения сырых данных в JSONB-формате. Подробнее в [raw_storage/README.md](src/bp1/raw_storage/README.md).

### Ключевые компоненты

- **`RawDataRepository`** — репозиторий для CRUD-операций: `save()`, `find_by_id()`, `find_by_content_hash()`, `find_by_trigger()`, `find_pending()`, `update_status()`, `find_by_prefix()`, `delete()`. По умолчанию дедуплицирует по хэшу содержимого `items` (`ContentHashDeduplicator`); стратегия заменяется через параметр `deduplicator`.
- **`StorageFactory`** — фабрика бэкендов: `create(backend_type)` и `register(name, backend_class)`. Доступен бэкенд `disk`.
- **`DiskBackend`** — JSONB-файлы на диске.

```python
import asyncio
from src.bp1.raw_storage import RawDataRepository, RawDataFile, StorageFactory

async def main():
    storage = StorageFactory.create('disk', base_path='./data/raw')
    repo = RawDataRepository(storage_backend=storage)

    file = RawDataFile(...)  # модель с meta + items
    path = await repo.save(file)
    print('Saved:', path)

    pending = await repo.find_pending()
    for f in pending:
        await repo.update_status(f.raw_id, 'processed')

asyncio.run(main())
```

## Хэширование и дедупликация

BP-1 использует трёхуровневую систему дедупликации:

1. **Redis** — хранит последний хэш для каждой `search_task_id`. При совпадении хэша строка RawItem не создаётся, обновляется только `updated_at`.
2. **MD5 от items** — [`calculate_content_hash()`](src/bp1/storage.py:46) считает хэш только от содержимого `items` (без `meta` и `file_path`), что позволяет детектировать смысловые изменения данных. Из `items` исключается поле `extra.file_path`.
3. **Bronze Layer** — `RawDataRepository` дедуплицирует файлы выгрузок по SHA-256 от содержимого `items` (`ContentHashDeduplicator`, см. [raw_storage/README.md](src/bp1/raw_storage/README.md)): повторное сохранение той же выгрузки возвращает путь к уже существующему файлу вместо создания второго.

## Функции и методы пакета (справочник)

### `storage.py`

| Класс / функция | Назначение |
|-----------------|-----------|
| [`RawDataService`](src/bp1/storage.py) | Единая персистентность: `persist()`, `persist_error()`, `save_raw_item()`, `update_timestamp()` |
| [`calculate_content_hash()`](src/bp1/storage.py:46) | MD5-хэш от канонического JSON `items` (без `meta` и `file_path`) |
| [`copy_html_file()`](src/bp1/storage.py) | Копирование HTML с retry (Windows PermissionError fallback) |
| [`save_raw_json()`](src/bp1/storage.py) | Сохранение raw JSON на диск |
| [`ensure_directories()`](src/bp1/storage.py:144) | Создание директорий для хранения данных |

### `jobs.py`

Публичный API для CLI и планировщика (Celery task/beat) — см.
[«Подключение к Celery»](#подключение-к-celery-tasks-и-beat).

| Функция | Назначение |
|---------|-----------|
| [`collect_source()`](src/bp1/jobs.py) | Один источник по всем активным конкурентам (`status='source_not_found'`, если источника нет в БД) |
| [`collect_competitor()`](src/bp1/jobs.py) | Один конкурент по всем активным источникам; конкурента, которого нет в БД, создаёт сам |
| [`collect_all()`](src/bp1/jobs.py) | Полный прогон: все активные источники × все активные конкуренты (`ensure_matrix` — достраивать связки или нет) |
| [`register_source()`](src/bp1/jobs.py) | Поставить источник на учёт: нормализация URL, классификация, запись `Source`, кэш, проверка поискового эндпоинта |

### `tasks.py`

| Функция | Назначение |
|---------|-----------|
| [`get_search_task_config()`](src/bp1/tasks.py) | Получение конфигурации задачи из БД (competitor, source, trigger, is_active) |
| [`get_parser_for_source()`](src/bp1/tasks.py) | Получение парсера из `ParserFactory` |
| [`_build_parse_kwargs()`](src/bp1/tasks.py) | Формирование URL поиска и kwargs для `parse()` по конфигурации |
| [`run_parser_async()`](src/bp1/tasks.py) | Основная асинхронная задача парсинга |

### `runner.py`

| Класс / функция | Назначение |
|-----------------|-----------|
| [`BPRunner`](src/bp1/runner.py:37) | Оркестратор: `run_all()`, `_get_active_tasks()`, `_get_tasks_by_ids()`, `_run_single_task()` |
| [`RunMode`](src/bp1/runner.py:173) | Константы режимов `DIRECT` / `CELERY` |
| [`run_pipeline()`](src/bp1/runner.py:180) | Асинхронная точка входа пайплайна |
| [`run_pipeline_sync()`](src/bp1/runner.py:275) | Синхронная обёртка |

### `base_parser.py`

| Класс / функция | Назначение |
|-----------------|-----------|
| [`ParsedItem`](src/bp1/base_parser.py:18) | Одна единица информации |
| [`ParsedResponse`](src/bp1/base_parser.py:64) | Результат одного похода на URL |
| [`BaseParser`](src/bp1/base_parser.py:115) | Абстрактный контракт парсера |
| [`ParserFactory`](src/bp1/base_parser.py:193) | Фабрика: `register()`, `get_parser()`, `list_sources()` |

### `adaptive/`

| Класс | Назначение |
|-------|-----------|
| `AdaptiveRunner` | Единая точка входа: `run_task()`, `run_all()`, `run_source_competitor()` |
| `AdaptiveBridgeParser` | Мост между Adaptive и `BaseParser` |
| `AdaptiveParser` | Интеллектуальный парсинг (LLM + селекторы + кэш) |
| `SourceClassifier` | Классификация источников и выбор стратегии |
| `AgenticOrchestrator` | Оркестрация стратегий с деградацией |
| `LLMClient` / `AIAgent` | Работа с LLM |
| `UnifiedCache` | Единый кэш (адаптеры — Redis, профили/HTML — диск) |
| `DataQualityGate` | 5 уровней контроля качества |
| `HITLManager` / `ProfileManager` | Решение CAPTCHA человеком + профили браузера |
| `SourceRegistrationService` | Регистрация источников по ссылке |
| `SearchParamResolver` | Source-aware выбор поискового параметра (ИНН / название) |
| `SearchUrlTemplateRegistry` | Per-source шаблоны URL поиска (fallback `/search?q=`) |

### `raw_storage/`

| Класс | Назначение |
|-------|-----------|
| `RawDataRepository` | Репозиторий JSONB-файлов (CRUD + дедупликация) |
| `StorageFactory` | Фабрика бэкендов (`create`, `register`) |
| `DiskBackend` | JSONB-хранение на диске |

## Тестирование

### Модульные тесты

```bash
# Все тесты BP-1
pytest kodik/tests/bp1/ -v

# Только fedresurs
pytest kodik/tests/bp1/fedresurs/ -v

# Только adaptive
pytest kodik/tests/bp1/adaptive/ -v

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

### Покрытие тестами (adaptive)

| Файл тестов | Что тестируется |
|-------------|-----------------|
| [`test_classifier.py`](kodik/tests/bp1/adaptive/test_classifier.py) | SourceClassifier — детекция типов, антибот, CAPTCHA, стратегии |
| [`test_orchestrator.py`](kodik/tests/bp1/adaptive/test_orchestrator.py) | AgenticOrchestrator — деградация стратегий |
| [`test_engines.py`](kodik/tests/bp1/adaptive/test_engines.py) | Crawl4AIStrategy, StealthStrategy, HITLStrategy |
| [`test_hitl.py`](kodik/tests/bp1/adaptive/test_hitl.py) | HITLManager, ProfileManager |
| [`test_parser.py`](kodik/tests/bp1/adaptive/test_parser.py) | AdaptiveParser — извлечение, селекторы, кэш |
| [`test_chunking.py`](kodik/tests/bp1/adaptive/test_chunking.py) | StructuredChunker, HtmlCleaner, ResultMerger |
| [`test_quality.py`](kodik/tests/bp1/adaptive/test_quality.py) | DataQualityGate — уровни качества, Quarantine |
| [`test_llm.py`](kodik/tests/bp1/adaptive/test_llm.py) | LLMClient, AIAgent — все методы, эвристический fallback и путь с ключом API |
| [`test_llm_smoke.py`](kodik/tests/bp1/adaptive/test_llm_smoke.py) | ✅ Сквозной smoke-тест LLM-модуля **на реальных сохранённых HTML-страницах** (`data/html_pages`) — см. [«Тесты LLM на реальных данных»](#тесты-llm-на-реальных-данных) |
| [`test_json_utils.py`](kodik/tests/bp1/adaptive/test_json_utils.py) | ✅ `parse_json` — устойчивый разбор ответа LLM (чистый JSON, markdown-фенс ` ```json `, текст до/после, невалидный ввод) |
| [`test_prompt_builders.py`](kodik/tests/bp1/adaptive/test_prompt_builders.py) | ✅ `build_classification_prompt`/`build_analysis_prompt`/`build_chunk_prompt`/`build_strategy_prompt`/`build_result_analysis_prompt`/`build_article_text_prompt` — подстановка реальных значений в промпты |
| [`test_integration.py`](kodik/tests/bp1/adaptive/test_integration.py) | AdaptiveRunner, AdaptiveBridgeParser |
| [`test_source_registration.py`](kodik/tests/bp1/adaptive/test_source_registration.py) | SourceRegistrationService, нормализация URL, проверка поискового эндпоинта |
| [`test_runner_source_aware.py`](kodik/tests/bp1/adaptive/test_runner_source_aware.py) | Source-aware выбор параметра (ИНН vs название), пробинг |
| [`test_runner_concurrency.py`](kodik/tests/bp1/adaptive/test_runner_concurrency.py) | Параллельное выполнение `run_all` (лимит, порядок, сессии) |
| [`test_search_probe.py`](kodik/tests/bp1/adaptive/test_search_probe.py) | Перебор параметров, POST-форма, переформулировки |

### Тесты общего контура

| Файл тестов | Что тестируется |
|-------------|-----------------|
| [`test_cli.py`](kodik/tests/bp1/test_cli.py) | Безопасная очистка ключей Redis (`clear-redis`) |
| [`test_raw_storage.py`](kodik/tests/bp1/test_raw_storage.py) | Дедупликация Bronze Layer по хэшу содержимого |
| [`test_pipeline_metrics.py`](kodik/tests/bp1/test_pipeline_metrics.py) | Сводка прогона: success_rate, стратегии, уровни качества |
| [`test_jobs.py`](kodik/tests/bp1/test_jobs.py) | ✅ Задания планировщика (`jobs.py`): идемпотентное «найти или создать», построение матрицы пар для всех трёх режимов сбора, JSON-сериализуемость результата, отсутствующий источник не даёт побочных эффектов. БД и Redis подменены фейками — тесты идут без внешних сервисов |
| [`test_raw_data_contract.py`](kodik/tests/bp1/test_raw_data_contract.py) | ✅ Контракт `raw_data` (`ParsedMeta`/`ParsedItem`/`ParsedMetrics`) против примера из `ABOUT_PROJECT/ABOUT.md`: закрытые поля `meta`/`items` (`extra='forbid'`), `metrics` не сериализуется в persisted `raw_data` |

### Тесты LLM на реальных данных

`test_llm_smoke.py` и `test_llm.py` — не игрушечные примеры на трёх строках
HTML. Фикстура `html_page` берёт **настоящие, реально скачанные страницы**
живых источников из [`data/html_pages/`](src/bp1/data/html_pages/)
(`lenta.ru`, `hh.ru`, `rbc.ru`, `iz.ru`, `kodik.ru`, `ria.ru` и др. —
снимки, сделанные адаптивным движком в ходе обычной работы) и прогоняет их
через весь реальный конвейер LLM-модуля:

`SourceClassifier.classify` → `LLMClient.analyze_structure` (с
авто-чанкированием) → `HtmlCleaner` → `StructuredChunker` → параллельное
извлечение по чанкам → `ResultMerger` → `AIAgent.choose_strategy` /
`AIAgent.analyze_result`.

Единственное, что в pytest подменяется — сетевой транспорт: вызов
`openai.AsyncOpenAI` перехватывается фейком, который возвращает
заранее заданный (но валидный по формату) ответ модели. Так тесты остаются
быстрыми, детерминированными и не требуют `LLM_API_KEY` в CI, но при этом
реально исполняют логику классификации, чанкирования, промптов и мержа на
неадаптированной боевой разметке сайтов — в отличие от синтетических
фикстур, здесь никто заранее не подгонял HTML под селекторы.

Оба пути покрыты явно:
- **эвристический fallback** (без `LLM_API_KEY`) — `test_smoke_*_heuristic`;
- **путь с LLM** (`LLM_API_KEY` задан, ответ приходит от фейкового клиента
  в реальном формате OpenAI Chat Completions) — `test_smoke_*_real_path`.

Для проверки **с настоящим обращением к провайдеру** (без фейка) есть
отдельный ручной скрипт — не автотест, `pytest` его не подхватывает
(`testpaths = ["tests"]` в `pyproject.toml` сюда не заглядывает):

```bash
# Требует реальный LLM_API_KEY в .env; делает настоящие вызовы к провайдеру
python -m src.bp1.adaptive.llm_test
```

Он прогоняет тот же самый конвейер (классификация → анализ структуры →
чанкирование → прямой анализ → выбор стратегии → анализ результата) на
первой странице из `data/html_pages/`, печатая селекторы, схему данных,
confidence и метаданные на каждом этапе — удобно для ручной проверки
качества промптов после их правки, до того как полагаться на детерминированные
фейковые тесты.

### Реальный прогон всего этапа

Сквозной прогон на живой БД/Redis выполняется точкой входа этапа:

```bash
# Требует: PostgreSQL + Redis + активные search_task в БД
python -m core.pipeline.cli 1 real
```

Возвращает сводку прогона (`success_rate`, разбивка по стратегиям и
уровням Quality Gate). Прежний ручной скрипт `src/bp1/test_parser.py`
удалён — его роль закрывают автотесты выше и эта команда.

## Настройка

### Переменные окружения (`.env`)

```ini
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/kodik

# Redis
REDIS_URL=redis://localhost:6379/0

# Корень для хранения данных. Поддиректории html_pages/ и raw/
# вычисляются от него (settings.bp1_html_dir / settings.bp1_raw_dir —
# свойства, отдельными переменными окружения не задаются).
BP1_DATA_ROOT=./src/bp1/data

# LLM (для адаптивного извлечения, классификации и обогащения)
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
# LLM_BASE_URL=https://...   # для совместимых с OpenAI провайдеров
```

### Ключевые эксплуатационные настройки

Меняются без правки кода; значения — по умолчанию.

```ini
# Охват сбора
BP1_MAX_NEWS_PER_SOURCE=20       # новостей с источника за прогон
BP1_MAX_PAGINATION_PAGES=10      # верхний предел страниц пагинации
BP1_MAX_CONCURRENT_TASKS=5       # параллельных задач в run_all
BP1_MAX_CONCURRENT_FETCHES=5     # параллельных докачек статей

# Релевантность и обогащение (LLM)
BP1_RELEVANCE_MODE=rank          # off | filter | rank
BP1_RELEVANCE_THRESHOLD=0.6      # порог для режима filter
BP1_ENRICHMENT_ENABLED=true

# Circuit breaker источников
SOURCE_CIRCUIT_TTL_SECONDS=86400
SOURCE_DISABLE_THRESHOLD=3       # подряд отказов -> is_active=False

# RSS/Atom/sitemap для новостных источников (SourceType.NEWS)
BP1_FEED_CACHE_TTL_SECONDS=604800        # кэш обнаружения фида (URL/«фида нет»), 7 дней
BP1_FEED_ITEMS_CACHE_TTL_SECONDS=3600    # кэш распарсенных материалов фида, 1 час
BP1_FEED_FAIL_THRESHOLD=2                # подряд отказов фида до сброса кэша обнаружения
```

`BP1_RELEVANCE_MODE=rank` (а не `filter`) — намеренный выбор по умолчанию:
BP-1 отвечает за сырой сбор (Bronze Layer), а решение «что из собранного
оставить» принадлежит этапу нормализации (BP-2). `rank` только размечает
и сортирует по `relevance`, ничего не отбрасывая.

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
- **BeautifulSoup4** — парсинг HTML (адаптивный движок)
- **crawl4ai** (опционально) — AI-краулинг для `CRAWL4AI`-стратегии
- **LLM-провайдер** (опционально) — для интеллектуального извлечения селекторов и данных

## План развития

- [x] Реализовать адаптивный движок (классификация, стратегии, LLM, HITL)
- [x] Интегрировать адаптивный движок с BP-1 пайплайном
- [x] Выделить `jobs.py` — контракт заданий, готовый для Celery task/beat
- [ ] Подключить `jobs.py`/`celery_tasks.py` к `beat_schedule` в проде
      (сейчас `include`/`beat_schedule` в `core/celery_app.py` пустые —
      рецепт подключения см. в разделе «Подключение к Celery: tasks и beat»)
