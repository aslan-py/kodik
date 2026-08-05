# BP-1 Adaptive — Адаптивный сбор данных

Интеллектуальная система сбора данных, которая автоматически определяет
структуру сайта, извлекает данные без предварительной настройки и
адаптируется к изменениям в реальном времени.

Пакет входит в состав BP-1 и полностью интегрирован с его пайплайном:
реализует `BaseParser`, сохраняет результаты в `RawItem`, использует
`SearchTask` из БД и Redis для дедупликации.

---

## Возможности

### Классификация источников
- [`SourceClassifier`](classifier.py) автоматически определяет тип сайта:
  новостной, реестр, API, SPA или неизвестный.
- Детектирует антибот-защиту (Cloudflare, DataDome, QRATOR, Akamai,
  Incapsula), CAPTCHA-виджеты (reCAPTCHA, hCaptcha) и SPA-фреймворки
  (React, Vue, Nuxt, Next.js).
- Вычисляет оценку сложности (0.0–1.0) и рекомендует оптимальную стратегию.

### Иерархия стратегий с деградацией
[`AgenticOrchestrator`](orchestrator.py) пробует стратегии по порядку и при
ошибке или недостаточном объёме контента (меньше 300 символов) переходит
к следующей, более «тяжёлой»:

```
FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL
```

| Стратегия | Движок | Назначение |
|-----------|--------|------------|
| `FAST` | `urllib` (stdlib) | Прямой HTTP-запрос |
| `CRAWL4AI` | `crawl4ai` | AI-краулинг с JS-рендерингом |
| `BROWSER` | Playwright | Браузерная автоматизация |
| `WAYBACK` | Internet Archive | Получение из архива |
| `STEALTH` | `collectors.stealth` | Обход антибот-защиты (инъекция стелса, QRATOR) |
| `HITL` | Playwright (видимый) | Решение CAPTCHA человеком |

Все стратегии реализованы в [`engines.py`](engines.py) и наследуют
`BaseStrategy`. Можно зарегистрировать собственную стратегию через
`AgenticOrchestrator.register_strategy()`.

### Интеллектуальный парсинг
- [`AdaptiveParser`](parser.py) анализирует структуру HTML, извлекает
  селекторы и схему данных без ручной настройки.
- Адаптеры кэшируются (Redis, TTL 7 дней) и переиспользуются при
  повторных обращениях к источнику.
- [`AdaptiveBridgeParser`](bridge.py) конвертирует результат в
  `ParsedResponse` для полной совместимости с BP-1.

### 5 уровней контроля качества
[`DataQualityGate`](quality.py) — пятиуровневая валидация с
Quarantine-паттерном:

1. **SCHEMA** — проверка обязательных полей (`url`, `title`).
2. **TYPES** — проверка типов данных.
3. **BUSINESS** — проверка бизнес-правил (например, минимальная длина).
4. **VOLUME** — мониторинг объёма (аларм при падении > 20%).
5. **CONSISTENCY** — проверка на дубликаты.

Проблемные записи помещаются в карантин (`QuarantineRecord`).

### HITL для CAPTCHA
- [`HITLManager`](hitl.py) запускает видимый браузер и ожидает решения
  CAPTCHA человеком.
- Результат (cookies) кэшируется в профиль браузера на диске и
  переиспользуется при следующих обращениях.

### Кэширование
[`UnifiedCache`](cache.py) хранит:
- **Адаптеры** — Redis, TTL 7 дней.
- **Профили браузеров** — диск (`cache_dir/profiles`).
- **HTML-снапшоты** — диск (`cache_dir/snapshots`).

### Логирование
Пакет использует стандартный модуль `logging` Python. Каждый модуль
получает логгер через `logging.getLogger(__name__)`. Модуль
[`logger.py`](logger.py) предоставляет тонкую обёртку `get_logger()`
и не создаёт хендлеры — конфигурация (`basicConfig`) выполняется в
точке входа (cli.py, runner.py и т.д.), чтобы избежать дублирования
сообщений.

### MCP-сервер
[`MCPServer`](mcp_server.py) реализует Model Context Protocol поверх
JSON-RPC 2.0 через stdio (без внешнего пакета `mcp`). Позволяет
ИИ-агентам (Claude, GPT и др.) управлять сбором данных.

Инструменты:
- `classify_source` — классифицировать источник.
- `run_adaptive_parse` — выполнить адаптивный парсинг.
- `list_strategies` — список стратегий обхода.
- `get_adapter` / `clear_adapter` — управление кэшем адаптеров.

### Полная интеграция с BP-1
- Реализует `BaseParser` через `AdaptiveBridgeParser`.
- [`AdaptiveRunner`](runner.py) выполняет полный цикл: получение задачи →
  классификация → парсинг → валидация → сохранение в `RawItem` →
  сохранение HTML/JSON на диск → обновление Redis (дедупликация).

---

## Структура

```
src/bp1/adaptive/
├── __init__.py              # Публичный API
├── schemas.py               # Pydantic-схемы
├── classifier.py            # SourceClassifier
├── orchestrator.py          # AgenticOrchestrator, BaseStrategy
├── engines.py               # Crawl4AIStrategy, StealthStrategy, HITLStrategy
├── parser.py                # AdaptiveParser
├── llm.py                   # LLMClient, AIAgent
├── quality.py               # DataQualityGate
├── hitl.py                  # HITLManager, ProfileManager
├── cache.py                 # UnifiedCache
├── logger.py                # get_logger (тонкая обёртка над logging)
├── bridge.py                # AdaptiveBridgeParser
├── runner.py                # AdaptiveRunner
├── mcp_server.py            # MCPServer
├── cli.py                   # CLI интерфейс
├── requirements.txt         # Зависимости пакета
└── README.md                # Этот файл
```

---

## Установка и настройка

### 1. Установка зависимостей

Из корня проекта `kodik/`:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # для тестов и линтера
```

Зависимости самого пакета перечислены в
[`requirements.txt`](requirements.txt) (pydantic, crawl4ai, litellm,
openai, playwright, sqlalchemy).

### 2. Установка браузера Playwright

`pip` ставит только библиотеку. Сами бинарники браузера (~150 МБ) качаются
отдельно. Без них BROWSER- и STEALTH-стратегии падают при старте браузера:

```bash
python -m playwright install chromium
```

### 3. Настройка окружения

Скопируйте `.env.example` в `.env` и подставьте свои значения:

```bash
cp .env.example .env
```

Обязательные переменные для работы `AdaptiveRunner` и CLI (Postgres, Redis):

```dotenv
POSTGRES_USER=admin
POSTGRES_PASSWORD=password
POSTGRES_DB=kodik_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=password
```

### 4. Настройка LLM

Пакет использует LLM для анализа структуры HTML и выбора стратегии обхода.
LLM-провайдер настраивается через переменные окружения (см.
[`llm.py`](llm.py)):

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `LLM_MODEL` | `gpt-4o-mini` | Модель LLM |
| `LLM_API_KEY` | — | Ключ API провайдера |
| `LLM_BASE_URL` | — | Базовый URL (для OpenAI-совместимых API) |
| `OPENAI_API_KEY` | — | Альтернативный ключ (OpenAI) |

Пример для OpenAI:

```dotenv
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

Пример для OpenAI-совместимого API (например, локальный Ollama или
прокси):

```dotenv
LLM_MODEL=ollama/llama3
LLM_BASE_URL=http://localhost:11434
LLM_API_KEY=ollama
```

> **Важно:** если `LLM_API_KEY` и `OPENAI_API_KEY` не заданы, пакет
> автоматически переключается на **эвристический fallback** (анализ HTML
> по тегам и выбор стратегии по классификации). Пакет остаётся полностью
> работоспособным без внешних LLM-сервисов.

### 5. Запуск инфраструктуры (Postgres + Redis)

Если используется `docker-compose.yml` из корня проекта:

```bash
docker compose up -d
```

---

## Использование

### Через CLI

```bash
# Классификация источника
python -m src.bp1.adaptive.cli classify --source lenta.ru

# Запуск адаптивного сбора (все активные задачи)
python -m src.bp1.adaptive.cli run

# Запуск конкретной задачи
python -m src.bp1.adaptive.cli run --task-id 26

# Запуск с указанием режима и fallback
python -m src.bp1.adaptive.cli run --source lenta.ru \
    --mode hybrid --fallback

# Управление кэшем адаптеров
python -m src.bp1.adaptive.cli cache --show --source lenta.ru
python -m src.bp1.adaptive.cli cache --clear --source lenta.ru

# Управление профилями браузеров
python -m src.bp1.adaptive.cli profile --show --source lenta.ru

# Отчёт качества
python -m src.bp1.adaptive.cli quality --report --task-id 26
```

### Через код

```python
from src.bp1.adaptive import AdaptiveRunner

runner = AdaptiveRunner(mode='adaptive', headless=True, timeout=60000)
# runner.run_task(task_id, session, redis_client)
# runner.run_all(session, redis_client)
```

Прямой парсинг без БД:

```python
import asyncio
from src.bp1.adaptive import AdaptiveParser

async def main():
    parser = AdaptiveParser(headless=True, timeout=60000)
    result = await parser.parse(
        url='https://lenta.ru/search?q=ИИ',
        source_name='lenta.ru',
        competitor='ООО АРХИТЕХ ИИ',
        trigger='ИИ',
    )
    print(result.status, len(result.items))

asyncio.run(main())
```

### Интеграция с ParserFactory

```python
from src.bp1.adaptive import AdaptiveBridgeParser
from src.bp1.base_parser import ParserFactory

ParserFactory.register('adaptive', AdaptiveBridgeParser)
ParserFactory.register('lenta.ru', lambda: AdaptiveBridgeParser(
    source_name='lenta.ru'
))
```

### Запуск MCP-сервера

```bash
python -m src.bp1.adaptive.mcp_server
```

Либо программно:

```python
from src.bp1.adaptive import run_mcp_server

run_mcp_server()
```

---

## Режимы работы

| Режим | Описание |
|-------|----------|
| `adaptive` | Только адаптивный парсинг |
| `hybrid` | Адаптивный + legacy fallback |
| `fallback` | adaptive → legacy → browser → wayback → HITL |

---

## Запуск тестов

Тесты пакета находятся в `kodik/tests/bp1/adaptive/`. Для их запуска
нужны `pytest` и `pytest-asyncio` (уже в `requirements-dev.txt`).

### Все тесты пакета

Из корня проекта `kodik/`:

```bash
pytest tests/bp1/adaptive -v
```

### Отдельный файл тестов

```bash
pytest tests/bp1/adaptive/test_classifier.py -v
pytest tests/bp1/adaptive/test_llm.py -v
pytest tests/bp1/adaptive/test_orchestrator.py -v  #
pytest tests/bp1/adaptive/test_engines.py -v
pytest tests/bp1/adaptive/test_quality.py -v
pytest tests/bp1/adaptive/test_parser.py -v  #
pytest tests/bp1/adaptive/test_mcp.py -v
pytest tests/bp1/adaptive/test_integration.py -v
```

### Все тесты проекта

```bash
pytest -v
```

### Линтер и форматтер

```bash
ruff check src/bp1/adaptive tests/bp1/adaptive
ruff format --check src/bp1/adaptive tests/bp1/adaptive
```

> **Примечание:** тесты используют фейковые оркестраторы и Redis-клиенты,
> поэтому не требуют запущенной инфраструктуры (Postgres/Redis). Тесты
> `test_engines.py` проверяют корректную обработку ошибок при недоступности
> `crawl4ai`/Playwright через `monkeypatch`.

---

## Зависимости

Полный список внешних зависимостей пакета — в
[`requirements.txt`](requirements.txt):

- `pydantic>=2.0` — Pydantic-схемы.
- `crawl4ai>=0.4.0` — AI-краулинг (CRAWL4AI-стратегия).
- `litellm>=1.40.0`, `openai>=1.0.0` — LLM-клиент.
- `playwright>=1.40` — браузерная автоматизация (BROWSER/STEALTH/HITL).
- `sqlalchemy>=2.0` — AsyncSession (runner, cli).

Внутренние модули репозитория, от которых зависит пакет:
`src.bp1.base_parser`, `src.bp1.tasks`, `src.bp1.models`,
`src.bp1.constants`, `src.bp1.collectors.stealth`, `core.config`,
`core.database`, `core.redis_client`.
