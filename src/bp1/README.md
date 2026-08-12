# BP-1: Сбор данных (Bronze Layer)

BP-1 — первый слой ETL-пайплайна системы конкурентной разведки. Отвечает за сбор сырых данных из внешних источников (федеральные реестры, API, сайты) и сохранение их в структурированном виде для последующей обработки в BP-2 (Silver Layer).

## Статус: ✅ РАБОТАЕТ

- **fedresurs.ru** — полностью реализован RPA-парсер с обходом QRATOR антибот-защиты
- **Адаптивный движок (adaptive)** — полностью реализован: автоматическая классификация источников, иерархия стратегий обхода с деградацией (FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL), интеллектуальное извлечение через LLM, кэширование адаптеров и CLI
- **Остальные источники** — обрабатываются универсальным `AdaptiveBridgeParser` (авто-детекция структуры сайта без ручной настройки)
- **Адаптивный поиск (Adaptive Search)** — полностью реализован: source-aware выбор поискового параметра (ИНН для гос. источников, название конкурента для остальных), per-source шаблоны URL поиска (например, `hh.ru → /search/vacancy?text=`), пропуск задач по `is_active`, circuit breaker (авто-блокировка источника при сбоях)
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
├── celery_tasks.py          # Celery-обёртка для production-запуска
├── cli.py                   # CLI-интерфейс (запуск, список задач, очистка Redis)
├── test_parser.py           # Интеграционный тест с реальной БД и Redis
│
├── parsers/                 # Адаптеры парсеров (реализуют BaseParser)
│   ├── __init__.py          # Регистрация адаптеров в ParserFactory
│   ├── fedresurs_adapter.py # ✅ fedresurs.ru (RPA, QRATOR bypass)
│   └── ...                  # Остальные источники — через универсальный AdaptiveBridgeParser
│
├── adaptive/                # ✅ Адаптивный сбор данных (интеллектуальный парсинг)
│   ├── schemas.py           # Pydantic-схемы (классификация, стратегии, HITL, отчёты)
│   ├── cli.py               # CLI: run / classify / add-source / cache / profile / quality
│   ├── core/                # UnifiedCache (Redis+диск), DataQualityGate (5 уровней)
│   ├── processing/          # AdaptiveParser, HtmlCleaner, StructuredChunker, ResultMerger, LLM
│   ├── strategies/          # SourceClassifier, AgenticOrchestrator, Crawl4AI/Stealth/HITL, engines
│   └── integration/         # AdaptiveBridgeParser, AdaptiveRunner, SourceRegistrationService
│
├── collectors/              # Движки парсинга (реализация сбора данных)
│   ├── fedresurs_rpa/       # ✅ RPA-парсер fedresurs.ru
│   └── stealth/             # ✅ Модуль антиобнаружения (QRATOR bypass, JS evasions)
│
└── raw_storage/             # ✅ Модуль хранения сырых данных (Bronze Layer)
    ├── core/models.py       # Pydantic модели (RawDataFile, MetaInfo, RawDataItem)
    ├── core/interfaces.py   # Абстрактные интерфейсы (BaseStorage, BaseDeduplicator)
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
способом, что и `AdaptiveRunner.run_all()` из адаптивного CLI.

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

### Адаптивный CLI (BP-1 Adaptive)

```bash
# Запуск всех задач из БД (учитывает is_active SearchTask/Source/Competitor)
python -m src.bp1.adaptive.cli run

# Сбор по конкретному источнику + конкуренту (создаёт Source/Competitor/SearchTask
# и запускает именно эту задачу — адаптивный поиск по паре)
python -m src.bp1.adaptive.cli run --source lenta.ru --competitor "ООО АРХИТЕХ ИИ"

# Гибридный режим с fallback
python -m src.bp1.adaptive.cli run --source lenta.ru --mode hybrid --fallback

# Классификация источника
python -m src.bp1.adaptive.cli classify --source lenta.ru

# Регистрация нового источника (нормализация + классификация + БД + Redis)
python -m src.bp1.adaptive.cli add-source --url "https://www.lenta.ru/news"

# Управление кэшем адаптеров (источник в любом виде: lenta.ru / https://lenta.ru/)
python -m src.bp1.adaptive.cli cache --show --source lenta.ru
python -m src.bp1.adaptive.cli cache --clear --source lenta.ru

# Управление профилями браузеров (HITL)
python -m src.bp1.adaptive.cli profile --show --source lenta.ru

# Отчёт качества по задаче
python -m src.bp1.adaptive.cli quality --report --task-id 26
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

```python
class ParsedResponse(BaseModel):
    meta: dict      # search_task_id, source, competitor, trigger, source_request_url, fetched_at
    items: list[ParsedItem]  # массив результатов

class ParsedItem(BaseModel):
    url: str              # ссылка на событие (обязательна)
    title: str            # заголовок (обязателен)
    text: str | None      # тело/описание
    published_at: str | None  # сырая дата
    region: str | None    # регион
    media_name: str | None    # СМИ/публикатор
    extra: dict           # источник-специфичные поля (file_path и др.)
```

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
- Поддержка прокси

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
- **Иерархия стратегий с деградацией** — [`AgenticOrchestrator`](src/bp1/adaptive/strategies/orchestrator.py:245) пробует стратегии по порядку `FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL`. При ошибке или контенте < 300 символов переходит к следующей.
- **Интеллектуальный парсинг** — [`AdaptiveParser`](src/bp1/adaptive/processing/parser.py:206) извлекает реальные CSS-селекторы и схему данных через LLM, кэширует адаптеры в Redis (TTL 7 дней).
- **Чанкирование больших страниц** — `HtmlCleaner → StructuredChunker → параллельное извлечение → ResultMerger` для HTML, не помещающегося в контекст LLM.
- **5 уровней контроля качества** — [`DataQualityGate`](src/bp1/adaptive/core/quality.py): SCHEMA, TYPES, BUSINESS, VOLUME, CONSISTENCY с Quarantine-паттерном.
- **HITL для CAPTCHA** — [`HITLManager`](src/bp1/adaptive/strategies/hitl.py) запускает видимый браузер, детектирует момент решения CAPTCHA и кэширует cookies в профиль.
- **Регистрация источников** — [`SourceRegistrationService`](src/bp1/adaptive/integration/sources.py:302) по ссылке нормализует адрес, классифицирует сайт, добавляет `Source` в БД и кэширует классификацию.
- **Source-aware выбор поискового параметра** — для гос. источников (реестры) поиск по ИНН, для остальных — по названию конкурента.
- **Per-source шаблоны URL** — `SearchUrlTemplateRegistry` задаёт специфичные пути поиска (например, `hh.ru → /search/vacancy?text=`), с fallback на универсальный `/search?q=`.

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
# Сбор по конкретному источнику + конкуренту: автоматически создаёт
# Source/Competitor/SearchTask и запускает адаптивный поиск по этой паре.
python -m src.bp1.adaptive.cli run --source hh.ru --competitor "ООО АРХИТЕХ ИИ"

# Гибридный режим с fallback
python -m src.bp1.adaptive.cli run --source lenta.ru --mode hybrid --fallback

# Все активные задачи (учитывает is_active всех трёх уровней)
python -m src.bp1.adaptive.cli run

# Регистрация нового источника (классификация + БД + Redis) перед поиском
python -m src.bp1.adaptive.cli add-source --url "https://hh.ru"
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

- **`RawDataRepository`** — репозиторий для CRUD-операций: `save()`, `find_by_id()`, `find_by_trigger()`, `find_pending()`, `update_status()`, `find_by_prefix()`, `delete()`. Поддерживает дедупликацию через `BaseDeduplicator`.
- **`StorageFactory`** — фабрика бэкендов: `create(backend_type)` и `register(name, backend_class)`. Доступен бэкенд `disk`.
- **`DiskBackend`** — JSONB-файлы на диске.

```python
import asyncio
from src.bp1.raw_storage import RawDataRepository, RawDataFile, StorageFactory

async def main():
    storage = StorageFactory.create('disk', base_dir='./data/raw')
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

BP-1 использует двухуровневую систему дедупликации:

1. **Redis** — хранит последний хэш для каждой `search_task_id`. При совпадении хэша строка RawItem не создаётся, обновляется только `updated_at`.
2. **MD5 от items** — [`calculate_content_hash()`](src/bp1/tasks.py:28) считает хэш только от содержимого `items` (без `meta` и `file_path`), что позволяет детектировать смысловые изменения данных. Из `items` исключается поле `extra.file_path`.

## Функции и методы пакета (справочник)

### `storage.py`

| Класс / функция | Назначение |
|-----------------|-----------|
| [`RawDataService`](src/bp1/storage.py) | Единая персистентность: `persist()`, `persist_error()`, `save_raw_item()`, `update_timestamp()` |
| [`calculate_content_hash()`](src/bp1/storage.py:46) | MD5-хэш от канонического JSON `items` (без `meta` и `file_path`) |
| [`copy_html_file()`](src/bp1/storage.py) | Копирование HTML с retry (Windows PermissionError fallback) |
| [`save_raw_json()`](src/bp1/storage.py) | Сохранение raw JSON на диск |
| [`ensure_directories()`](src/bp1/storage.py:144) | Создание директорий для хранения данных |

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
| [`test_llm.py`](kodik/tests/bp1/adaptive/test_llm.py) | LLMClient, AIAgent |
| [`test_llm_smoke.py`](kodik/tests/bp1/adaptive/test_llm_smoke.py) | Smoke-тест LLM-модуля |
| [`test_integration.py`](kodik/tests/bp1/adaptive/test_integration.py) | AdaptiveRunner, AdaptiveBridgeParser |
| [`test_source_registration.py`](kodik/tests/bp1/adaptive/test_source_registration.py) | SourceRegistrationService, нормализация URL |

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

# LLM (для адаптивного извлечения)
# OPENAI_API_KEY=sk-...
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
- **BeautifulSoup4** — парсинг HTML (адаптивный движок)
- **crawl4ai** (опционально) — AI-краулинг для `CRAWL4AI`-стратегии
- **LLM-провайдер** (опционально) — для интеллектуального извлечения селекторов и данных

## План развития

- [x] Реализовать адаптивный движок (классификация, стратегии, LLM, HITL)
- [x] Интегрировать адаптивный движок с BP-1 пайплайном
