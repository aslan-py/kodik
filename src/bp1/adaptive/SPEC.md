# Спецификация пакета `src.bp1.adaptive`

> **Статус документа:** актуальная спецификация для дальнейшей настройки пакета.
> **Дата:** 2026-08-05
> **Пакет:** `kodik/src/bp1/adaptive`

Документ отражает **реальное** состояние кода: что работает, что выполнено
в заглушках, а что требует переработки. Описаны точки входа, данные на
выходе, схемы, модели, методы и зависимости, необходимые для настройки.

---

## 1. Назначение пакета

Интеллектуальная система сбора данных, которая автоматически определяет
структуру сайта, извлекает данные без предварительной настройки и
адаптируется к изменениям. Входит в состав BP-1, реализует `BaseParser`,
сохраняет результаты в `RawItem`, использует `SearchTask` из БД и Redis
для дедупликации.

---

## 2. Структура пакета

```
src/bp1/adaptive/
├── __init__.py        # Публичный API (экспорт классов)
├── schemas.py         # Pydantic-схемы (модели данных)
├── classifier.py      # SourceClassifier — классификация источников
├── orchestrator.py    # AgenticOrchestrator, BaseStrategy, стратегии FAST/BROWSER/WAYBACK
├── engines.py         # Crawl4AIStrategy, StealthStrategy, HITLStrategy
├── parser.py          # AdaptiveParser — интеллектуальный парсинг
├── llm.py             # LLMClient, AIAgent — LLM-анализ и принятие решений
├── quality.py         # DataQualityGate — 5 уровней контроля качества
├── hitl.py            # HITLManager, ProfileManager — Human-in-the-Loop
├── cache.py           # UnifiedCache — кэширование (Redis + диск)
├── logger.py          # get_logger, new_trace_id
├── bridge.py          # AdaptiveBridgeParser — мост к BaseParser BP-1
├── runner.py          # AdaptiveRunner — единая точка входа
├── mcp_server.py      # MCPServer — MCP-сервер (JSON-RPC 2.0 / stdio)
├── cli.py             # CLI интерфейс
├── llm_test.py        # Smoke-тест LLM-модуля
├── requirements.txt   # Зависимости пакета
├── README.md          # Документация
└── SPEC.md            # Этот файл
```

---

## 3. Точки входа

| Точка входа | Способ вызова | Назначение |
|-------------|---------------|------------|
| **CLI** | `python -m src.bp1.adaptive.cli` | Команды `run`, `classify`, `cache`, `profile`, `quality` |
| **MCP-сервер** | `python -m src.bp1.adaptive.mcp_server` | Управление сбором через MCP (JSON-RPC 2.0 / stdio) |
| **AdaptiveRunner** | `AdaptiveRunner.run_task()/run_all()` | Полный цикл сбора с сохранением в БД/Redis |
| **AdaptiveParser** | `AdaptiveParser.parse()` | Прямой парсинг без БД |
| **AdaptiveBridgeParser** | `AdaptiveBridgeParser.parse()` | Реализация `BaseParser` для интеграции с BP-1 |
| **Smoke-тест LLM** | `python -m src.bp1.adaptive.llm_test` | Проверка LLM-анализа структуры |

---

## 4. Схемы и модели данных (`schemas.py`)

Все модели — Pydantic `BaseModel`. Перечислены с полями и назначением.

### 4.1 Классификация источника

**`SourceType`** (StrEnum): `NEWS='news'`, `REGISTRY='registry'`,
`API='api'`, `SPA='spa'`, `UNKNOWN='unknown'`.

**`SourceClassification`** — результат классификации:
| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `source_name` | `str` | — | Имя источника |
| `source_type` | `SourceType` | `UNKNOWN` | Тип сайта |
| `complexity_score` | `float` | `0.0` (0–1) | Оценка сложности обхода |
| `has_antibot` | `bool` | `False` | Наличие антибот-защиты |
| `has_captcha` | `bool` | `False` | Наличие CAPTCHA |
| `is_spa` | `bool` | `False` | SPA-приложение |
| `recommended_strategy` | `str` | `'FAST'` | Рекомендуемая стратегия |

### 4.2 Стратегии обхода

**`StrategyType`** (StrEnum): `FAST`, `CRAWL4AI`, `BROWSER`, `WAYBACK`,
`STEALTH`, `HITL`.

**`StrategyResult`** — результат выполнения стратегии:
| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `strategy` | `StrategyType` | — | Использованная стратегия |
| `success` | `bool` | `False` | Успех |
| `data` | `str \| None` | `None` | HTML-контент |
| `content_length` | `int` | `0` | Длина контента |
| `error` | `str \| None` | `None` | Ошибка |
| `elapsed_ms` | `int` | `0` | Длительность, мс |
| `used_cache` | `bool` | `False` | Использован ли кэш |

### 4.3 Адаптеры

**`AdapterConfig`** — конфигурация адаптера:
`source_name`, `base_url`, `adaptive=True`, `auto_save=True`,
`min_text_length=300`, `timeout_ms=60000`, `expected_schema={}`.

**`AdapterState`** — состояние адаптера в кэше:
`source_name`, `selectors={}`, `schema_config={}`, `confidence=0.0`,
`version=1`, `created_at`, `last_used_at`, `fail_count=0`.

**`AdaptiveParseResult`** — результат адаптивного парсинга:
| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `status` | `str` | `'ok'` | `ok` / `low_quality` / `error` |
| `source_name` | `str` | — | Источник |
| `url` | `str` | — | URL |
| `strategy_used` | `StrategyType` | `FAST` | Использованная стратегия |
| `items` | `list[dict]` | `[]` | Извлечённые элементы |
| `raw_text` | `str \| None` | `None` | Сырой HTML |
| `error` | `str \| None` | `None` | Ошибка |
| `adapter_version` | `int \| None` | `None` | Версия адаптера |
| `elapsed_ms` | `int` | `0` | Длительность |
| `trace_id` | `str \| None` | `None` | Идентификатор трассировки |

### 4.4 Контроль качества

**`QualityGateLevel`** (StrEnum): `SCHEMA`, `TYPES`, `BUSINESS`, `VOLUME`,
`CONSISTENCY`.

**`QualityGateReport`**: `level`, `passed=True`, `errors=[]`, `warnings=[]`,
`item_count=0`, `passed_count=0`, `quarantined_count=0`.

**`QuarantineRecord`**: `id`, `original_data`, `errors=[]`, `source`,
`created_at`, `resolved=False`.

### 4.5 HITL

**`HITLRequest`**: `request_id`, `url`, `challenge_type='captcha'`,
`profile_id=None`, `created_at`, `status='pending'`.

**`HITLResponse`**: `request_id`, `success=False`, `profile_id=None`,
`cookies={}`, `error=None`.

### 4.6 MCP

**`MCPTool`**: `name`, `description`, `parameters={}`.

### 4.7 Конфигурация и отчёты

**`UnifiedConfig`**: `mode='adaptive'`, `headless=True`, `timeout=60000`,
`adaptive_config=None`, `quality_gate_enabled=True`, `cache_profiles=True`,
`max_concurrent=5`.

**`PipelineStage`**: `name`, `status='ok'`, `duration_ms=0`, `detail={}`.

**`PipelineReport`**: `pipeline_id`, `mode`, `started_at`, `finished_at`,
`total_duration_ms`, `stages=[]`, `overall_status='ok'`.

> **Примечание:** `UnifiedConfig`, `PipelineStage`, `PipelineReport`
> определены в схемах, но **не используются** в текущем коде (нет
> пайплайна, который их заполнял бы). Требуют переработки/подключения.

---

## 5. Компоненты и их состояние

### 5.1 `classifier.py` — `SourceClassifier` ✅ РАБОТАЕТ

**Методы:**
- `async classify(source_name, source_url, headers=None, html=None) -> SourceClassification` — главный метод.
- `_detect_source_type(source_name, source_url) -> SourceType` — по имени/URL.
- `_get_known_source(source_name, source_url)` — база известных источников.
- `_detect_antibot(headers, html) -> bool` — маркеры Cloudflare/DataDome/QRATOR/Akamai/Incapsula.
- `_detect_captcha(html) -> bool` — reCAPTCHA/hCaptcha.
- `_detect_spa(html) -> bool` — React/Vue/Nuxt/Next/Angular.
- `_compute_complexity(...) -> float` — оценка 0.0–1.0.
- `_pick_strategy(...) -> StrategyType` — выбор стратегии.

**Логика выбора стратегии:**
```
API → FAST
CAPTCHA → HITL
ANTIBOT → STEALTH
SPA → BROWSER
иначе → FAST
```

**База известных источников** (`_KNOWN_SOURCES`): `fedresurs.ru`,
`kad.arbitr.ru` (QRATOR+SPA), `zakupki.gov.ru`, `nalog.ru`,
`egrul.nalog.ru` (антибот), `fips.ru` (статический).

**Состояние:** полностью реализован, покрыт тестами
(`tests/bp1/adaptive/test_classifier.py`). Работает без внешних сервисов.

---

### 5.2 `orchestrator.py` — `AgenticOrchestrator` ✅ РАБОТАЕТ

**Иерархия деградации** (`_DEGRADATION_ORDER`):
```
FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL
```

**`BaseStrategy`** (ABC): абстрактный метод `async fetch(url, **kwargs) -> StrategyResult`.

**Встроенные стратегии:**
- **`FastStrategy`** ✅ — прямой HTTP через `urllib` (stdlib), User-Agent Chrome.
- **`BrowserStrategy`** ✅ — Playwright, корректно освобождает ресурсы через `asyncio.shield`.
- **`WaybackStrategy`** ✅ — Internet Archive (`archive.org/wayback/available`).

**`AgenticOrchestrator`:**
- `__init__(headless=True, timeout_ms=60000, profiles_dir, logger)`.
- `_register_strategies()` — собирает реальные стратегии из `engines.build_default_strategies()`.
- `register_strategy(strategy_type, strategy)` — регистрация пользовательской стратегии.
- `async fetch_with_degradation(url, start_with=None, **kwargs) -> StrategyResult` — перебор стратегий по порядку, успех при `content_length >= 300`.
- `async fetch_with_timeout(url, timeout_ms=30000, cleanup_timeout_s=5.0, **kwargs) -> StrategyResult` — глобальный таймаут с корректной отменой и cleanup.

**Состояние:** полностью реализован, покрыт тестами
(`test_orchestrator.py`). `MIN_CONTENT_LENGTH = 300`.

---

### 5.3 `engines.py` — реальные движки стратегий ✅ РАБОТАЮТ (при наличии зависимостей)

**`Crawl4AIStrategy`** — AI-краулинг через `crawl4ai` (`AsyncWebCrawler`).
- Требует установки `crawl4ai>=0.4.0`.
- При отсутствии пакета возвращает `success=False` с ошибкой.

**`StealthStrategy`** — обход антибот-защиты через `src.bp1.collectors.stealth`.
- Использует `apply_stealth`, `bypass_qrator`, `get_context_config`, `get_launch_args`.
- При 401/403 вызывает `bypass_qrator`.
- Требует Playwright + бинарники chromium.

**`HITLStrategy`** — Human-in-the-Loop через `HITLManager`.
- Запускает видимый браузер, ждёт решения CAPTCHA человеком.

**`build_default_strategies(headless, timeout_ms, profiles_dir, logger) -> dict[StrategyType, BaseStrategy]`**
— собирает все 6 стратегий.

**Состояние:** реальные реализации, но **зависят от внешних пакетов**
(`crawl4ai`, `playwright`, `collectors.stealth`). Без них стратегии падают
с `success=False`. Покрыты тестами (`test_engines.py`).

---

### 5.4 `parser.py` — `AdaptiveParser` ⚠️ РАБОТАЕТ, НО ЕСТЬ ОГРАНИЧЕНИЯ

**Поток `parse()`:**
1. Проверка кэша адаптеров (`get_adapter`).
2. Получение HTML через оркестратор (с учётом кэшированной классификации → `start_with`).
3. Если адаптера нет → `LLMClient.analyze_structure()` → генерация `AdapterState`.
4. Парсинг HTML в элементы (`_parse_items`).
5. Валидация качества (`DataQualityGate.validate_all`).
6. Возврат `AdaptiveParseResult`.

**Вспомогательные классы:**
- `_matches_selector(tag, attrs, selector)` — поддержка простых CSS-селекторов (`tag`, `.class`, `#id`, комбинации).
- `_SelectorCollector(HTMLParser)` — извлечение по селекторам адаптера.
- `_LinkCollector(HTMLParser)` — эвристический сбор ссылок+заголовков.
- `_parse_items(html, source_name, competitor, trigger, selectors)` — извлечение элементов (до 50).

**Ограничения / требует переработки:**
- **Селекторы адаптера генерируются пустыми**: в `parse()` при отсутствии адаптера
  `selectors=dict.fromkeys(config.expected_schema, '')` — т.е. `container` пуст,
  поэтому реально используется только эвристический `_LinkCollector` (сбор ссылок).
  LLM-анализ структуры **не заполняет реальные CSS-селекторы**.
- `_SelectorCollector` — упрощённый HTMLParser, не поддерживает вложенные
  контейнеры корректно (стек обрабатывается наивно).
- `expected_schema` из `AdapterConfig` не передаётся в `_parse_items` как
  селекторы — связь между LLM-схемой и реальным извлечением **разорвана**.

**Состояние:** базовый парсинг работает (эвристика по ссылкам), но
"интеллектуальное" извлечение по селекторам фактически **не задействовано**.
Покрыт тестами (`test_parser.py`).

---

### 5.5 `llm.py` — `LLMClient`, `AIAgent` ⚠️ РАБОТАЕТ С FALLBACK

**`LLMClient`:**
- `async analyze_structure(html, competitor, expected_fields=None) -> AdapterConfig`.
- `_llm_analyze(...)` — через `litellm.acompletion`.
- `_heuristic_analyze(...)` — fallback без LLM (возвращает `AdapterConfig` с пустой схемой).
- `_parse_json(content)` — извлечение JSON из ответа (устойчив к markdown).

**`AIAgent`:**
- `async choose_strategy(classification) -> StrategyType`.
- `_llm_choose_strategy(...)` — через LLM.
- `_heuristic_strategy(classification)` — fallback.
- `async analyze_result(html, items, source_name) -> dict` — рекомендации.

**Конфигурация LLM** (переменные окружения):
| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `LLM_MODEL` | `gpt-4o-mini` | Модель |
| `LLM_API_KEY` | — | Ключ API |
| `LLM_BASE_URL` | — | Базовый URL (OpenAI-совместимые) |
| `OPENAI_API_KEY` | — | Альтернативный ключ |

**Состояние:** работает. Без `LLM_API_KEY`/`OPENAI_API_KEY` переключается
на эвристический fallback. **Ограничение:** fallback не извлекает реальные
селекторы — возвращает пустую схему (см. 5.4). Покрыт тестами
(`test_llm.py`), есть smoke-тест `llm_test.py`.

---

### 5.6 `quality.py` — `DataQualityGate` ✅ РАБОТАЕТ

**5 уровней валидации:**
1. `validate_schema(data, expected_schema=None)` — обязательные поля `url`, `title`.
2. `validate_types(items, type_map=None)` — проверка типов.
3. `validate_business_rules(items, rules=None)` — бизнес-правила (`min_length`).
4. `validate_volume(current_count, expected_count, threshold=0.8)` — мониторинг объёма.
5. `validate_consistency(items, key_field='url')` — дубликаты.

**Агрегация:**
- `validate_all(items, ...) -> list[QualityGateReport]` — все 5 уровней + карантин.
- `is_all_passed(reports) -> bool`.
- `quarantine(data, errors) -> QuarantineRecord` — Quarantine-паттерн.
- `quarantine_store` — список записей карантина.

**Состояние:** полностью реализован, покрыт тестами (`test_quality.py`).
Карантин хранится **в памяти** (не персистентен).

---

### 5.7 `hitl.py` — `HITLManager`, `ProfileManager` ⚠️ РАБОТАЕТ, НО УПРОЩЁН

**`ProfileManager`:**
- `get_profile(source_name) -> str | None` — путь к профилю.
- `create_profile(source_name) -> str` — создание профиля.
- `update_profile(profile_id, cookies)` — обновление cookies.

**`HITLManager`:**
- `async handle_challenge(url, source_name, challenge_type='captcha', timeout_s=120) -> HITLResponse`.
- `_launch_browser(url, timeout_s)` — видимый Playwright, ожидание CAPTCHA.
- `async check_status(request_id) -> HITLRequest`.
- `resolve(request_id, cookies=None) -> HITLResponse`.

**Ограничения / требует переработки:**
- `_launch_browser` просто ждёт `timeout_s` секунд (`wait_for_timeout`), **не
  детектирует** фактическое решение CAPTCHA. Нет обратной связи с человеком.
- Запросы хранятся в памяти (`self._requests`), не персистентны.
- Профиль хранит только cookies (dict), без полноценного состояния сессии.
- `HITLStrategy` возвращает `data=''` и `content_length=0` даже при успехе —
  **не передаёт HTML** дальше в пайплайн.

**Состояние:** базовая логика работает, но HITL-поток требует доработки
для реального использования. Покрыт тестами (в `test_engines.py`).

---

### 5.8 `cache.py` — `UnifiedCache` ✅ РАБОТАЕТ

**Хранилища:**
| Данные | Где | Ключ/путь | TTL |
|--------|-----|-----------|-----|
| Адаптеры | Redis | `bp1:adapter:{source_name}` | 7 дней |
| Классификации | Redis | `bp1:classification:{source_name}` | 7 дней |
| Профили браузеров | диск | `cache_dir/profiles/{source}.json` | — |
| HTML-снапшоты | диск | `cache_dir/snapshots/{md5(url)}.html` | — |

**Методы:**
- Адаптеры: `get_adapter`, `set_adapter`, `clear_adapter`.
- Классификации: `get_classification`, `set_classification`, `clear_classification`.
- Профили: `get_profile`, `set_profile`.
- Снапшоты: `get_snapshot`, `set_snapshot`.

**Состояние:** полностью реализован. Без Redis-клиента адаптеры и
классификации просто не кэшируются (возвращают `None`), диск работает всегда.
**Примечание:** HTML-снапшоты и профили в `UnifiedCache` **не используются**
в текущем пайплайне (профили дублируются в `ProfileManager`).

---

### 5.9 `bridge.py` — `AdaptiveBridgeParser` ✅ РАБОТАЕТ

Реализует `BaseParser` из `src.bp1.base_parser`.

**Методы:**
- `__init__(headless=True, timeout=60000, source_name='adaptive', redis_client=None)`.
- `async parse(url, **kwargs) -> ParsedResponse` — вызывает `AdaptiveParser.parse()`,
  конвертирует `AdaptiveParseResult.items` → `ParsedItem`, формирует `meta`.
- `get_source_name() -> str`.
- `get_parser_type() -> str` (возвращает `'adaptive'`).
- `bind_redis(redis_client)`.

**Выходной `meta`:**
```json
{
  "search_task_id": ...,
  "source": "adaptive",
  "competitor": ...,
  "trigger": ...,
  "source_request_url": ...,
  "strategy_used": "FAST",
  "trace_id": ...
}
```

**Состояние:** работает. При `status == 'error'` бросает `RuntimeError`.

---

### 5.10 `runner.py` — `AdaptiveRunner` ✅ РАБОТАЕТ (основной сценарий)

**Режимы:** `adaptive`, `hybrid`, `fallback`.

**`run_task(task_id, session, redis_client, **kwargs) -> dict`:**
1. Получить конфигурацию задачи (`get_search_task_config`).
2. Классифицировать источник (с кэшированием в Redis).
3. Сформировать URL: `https://{source}/search?q={param}`.
4. Выбрать парсер: специализированный RPA (из `ParserFactory`) или универсальный `AdaptiveBridgeParser`.
5. Сериализовать, вычислить хэш (`calculate_content_hash`).
6. Сверить через Redis (дедупликация) → `unchanged` / `new` / `changed`.
7. Сохранить HTML + JSON на диск (`settings.bp1_html_dir`, `bp1_raw_dir`).
8. Сохранить в `RawItem` (`save_raw_item`).
9. Обновить Redis.

**Возвращаемые статусы:** `skipped` (неактивна), `error`, `unchanged`,
`saved` (с `status_type` = `new`/`changed`).

**`run_all(session, redis_client, task_ids=None) -> list[dict]`** — все активные задачи.

**Состояние:** работает. Зависит от `core.config.settings`, `src.bp1.tasks`,
`src.bp1.models`, `src.bp1.parsers.ParserFactory`. Покрыт тестами
(`test_integration.py`).

---

### 5.11 `mcp_server.py` — `MCPServer` ✅ РАБОТАЕТ

MCP поверх JSON-RPC 2.0 через stdio (без внешнего пакета `mcp`).

**Протокол:** `MCP_PROTOCOL_VERSION = '2024-11-05'`, сервер `bp1-adaptive` v1.0.0.

**Методы JSON-RPC:** `initialize`, `tools/list`, `tools/call`,
`resources/list`, `notifications/initialized`.

**Инструменты:**
| Инструмент | Параметры | Назначение |
|------------|-----------|------------|
| `classify_source` | `source_name`, `source_url` | Классификация |
| `run_adaptive_parse` | `url`, `source_name`, `competitor`, `trigger` | Парсинг |
| `list_strategies` | — | Список стратегий |
| `get_adapter` | `source_name` | Получить адаптер |
| `clear_adapter` | `source_name` | Очистить адаптер |

**`serve(stdin=None, stdout=None)`** — цикл чтения JSON-RPC из stdin.

**Состояние:** работает. Покрыт тестами (`test_mcp.py`).
**Примечание:** `resources/list` возвращает пустой список (ресурсы не реализованы).

---

### 5.12 `cli.py` — CLI ✅ РАБОТАЕТ

**Команды:**
| Команда | Флаги | Назначение |
|---------|-------|------------|
| `run` | `--source`, `--competitor`, `--mode`, `--fallback`, `--task-id`, `--no-headless`, `--timeout` | Запуск сбора |
| `classify` | `--source` | Классификация |
| `cache` | `--source`, `--show`, `--clear` | Управление кэшем адаптеров |
| `profile` | `--source`, `--show` | Профили браузеров |
| `quality` | `--report`, `--task-id` | Отчёт качества |

**Состояние:** работает. Зависит от `core.database.AsyncSessionLocal`,
`core.redis_client.get_redis`, `src.bp1.models.RawItem`.

---

### 5.13 `logger.py` ✅ РАБОТАЕТ

- `get_logger(name='bp1_adaptive')` — тонкая обёртка над `logging.getLogger`.
- `new_trace_id() -> str` — генерация `uuid4().hex`.

**Состояние:** работает. Не создаёт хендлеры (конфигурация — в точке входа).

---

### 5.14 `__init__.py` ✅ РАБОТАЕТ

Экспортирует публичный API: `AdaptiveRunner`, `AdaptiveParser`,
`AdaptiveBridgeParser`, `AgenticOrchestrator`, `SourceClassifier`,
`DataQualityGate`, `HITLManager`, `ProfileManager`, `LLMClient`, `AIAgent`,
`MCPServer`, `run_mcp_server`, `UnifiedCache`, `get_logger`, все стратегии
и схемы.

---

## 6. Данные на выходе

### 6.1 `AdaptiveParseResult` (прямой парсинг)
```json
{
  "status": "ok",
  "source_name": "lenta.ru",
  "url": "https://lenta.ru/search?q=ИИ",
  "strategy_used": "FAST",
  "items": [
    {
      "url": "...",
      "title": "...",
      "text": null,
      "published_at": null,
      "region": null,
      "media_name": "lenta.ru",
      "extra": {"competitor": "...", "trigger": "..."}
    }
  ],
  "raw_text": "<html>...",
  "adapter_version": 1,
  "elapsed_ms": 1234,
  "trace_id": "abc123"
}
```

### 6.2 `ParsedResponse` (через `AdaptiveBridgeParser`)
```json
{
  "meta": {
    "search_task_id": 1,
    "source": "adaptive",
    "competitor": "...",
    "trigger": "...",
    "source_request_url": "...",
    "strategy_used": "FAST",
    "trace_id": "..."
  },
  "items": [ { "url": "...", "title": "...", "text": null, ... } ]
}
```

### 6.3 Результат `AdaptiveRunner.run_task()`
```json
{
  "status": "saved",
  "search_task_id": 1,
  "raw_item_id": 42,
  "hash": "md5...",
  "status_type": "new",
  "html_file_path": "...",
  "raw_file_path": "...",
  "strategy": "FAST"
}
```

---

## 7. Зависимости

### 7.1 Внешние пакеты (`requirements.txt`)
| Пакет | Версия | Использование |
|-------|--------|---------------|
| `pydantic` | `>=2.0,<3.0` | Схемы |
| `crawl4ai` | `>=0.4.0` | CRAWL4AI-стратегия |
| `litellm` | `>=1.40.0` | LLM-клиент |
| `openai` | `>=1.0.0` | OpenAI-совместимый API |
| `playwright` | `>=1.40,<2.0` | BROWSER/STEALTH/HITL |
| `sqlalchemy` | `>=2.0,<3.0` | AsyncSession |

> **Внимание:** бинарники Playwright ставятся отдельно:
> `python -m playwright install chromium`.

### 7.2 Внутренние модули репозитория
- `src.bp1.base_parser` — `BaseParser`, `ParsedItem`, `ParsedResponse`, `ParserFactory`.
- `src.bp1.tasks` — `calculate_content_hash`, `get_search_task_config`, `save_raw_item`, `update_timestamp`.
- `src.bp1.models` — `RawItem`, `SearchTask`.
- `src.bp1.constants` — `DEFAULT_TIMEOUT_MS`.
- `src.bp1.collectors.stealth` — `apply_stealth`, `bypass_qrator`, `get_context_config`, `get_launch_args`.
- `src.bp1.parsers` — `ParserFactory` (специализированные RPA-парсеры).
- `core.config` — `settings` (`bp1_html_dir`, `bp1_raw_dir`).
- `core.database` — `AsyncSessionLocal`.
- `core.redis_client` — `get_redis`.

---

## 8. Сводка состояния компонентов

| Компонент | Статус | Комментарий |
|-----------|--------|-------------|
| `SourceClassifier` | ✅ Работает | Полная реализация, тесты |
| `AgenticOrchestrator` | ✅ Работает | Деградация, таймауты, тесты |
| `FastStrategy` | ✅ Работает | urllib |
| `BrowserStrategy` | ✅ Работает | Playwright, cleanup |
| `WaybackStrategy` | ✅ Работает | Internet Archive |
| `Crawl4AIStrategy` | ⚠️ Зависит от пакета | Без `crawl4ai` → fail |
| `StealthStrategy` | ⚠️ Зависит от пакета | Без `collectors.stealth`/Playwright → fail |
| `HITLStrategy` | ⚠️ Упрощён | Не передаёт HTML, нет детекции решения |
| `AdaptiveParser` | ⚠️ Ограничен | Селекторы не заполняются, работает эвристика |
| `LLMClient` / `AIAgent` | ⚠️ Fallback | Без ключа — эвристика, селекторы пустые |
| `DataQualityGate` | ✅ Работает | 5 уровней, карантин в памяти |
| `HITLManager` | ⚠️ Упрощён | Нет детекции CAPTCHA, запросы в памяти |
| `UnifiedCache` | ✅ Работает | Redis + диск |
| `AdaptiveBridgeParser` | ✅ Работает | Конвертация в ParsedResponse |
| `AdaptiveRunner` | ✅ Работает | Полный цикл с БД/Redis |
| `MCPServer` | ✅ Работает | JSON-RPC 2.0 / stdio |
| `CLI` | ✅ Работает | 5 команд |
| `logger.py` | ✅ Работает | Обёртка над logging |
| `UnifiedConfig`/`PipelineReport` | ⚠️ Не используется | Определены, но не задействованы |

---

## 9. Что требует переработки (приоритеты)

### 🔴 Высокий приоритет

1. **Разрыв между LLM-анализом и извлечением селекторов** (`parser.py`, `llm.py`).
   - `LLMClient.analyze_structure()` возвращает `AdapterConfig.expected_schema`,
     но `AdaptiveParser` создаёт `AdapterState.selectors` как пустые строки
     (`dict.fromkeys(config.expected_schema, '')`).
   - **Нужно:** заставить LLM возвращать реальные CSS-селекторы
     (`{"selectors": {...}, "schema": {...}}`) и передавать их в `AdapterState.selectors`.
   - Сейчас фактически работает только эвристический `_LinkCollector`.

2. **HITL-поток** (`hitl.py`, `engines.py`).
   - `_launch_browser` ждёт фиксированный таймаут, не детектирует решение CAPTCHA.
   - `HITLStrategy` возвращает `data=''`, `content_length=0` — HTML не доходит
     до пайплайна.
   - **Нужно:** детекция решения (например, по изменению cookies/URL), передача
     HTML после решения, персистентность запросов.

### 🟡 Средний приоритет

3. **`_SelectorCollector`** (`parser.py`) — упрощённый HTMLParser, некорректно
   обрабатывает вложенные контейнеры. Рекомендуется заменить на
   `selectolax`/`BeautifulSoup`/`lxml` для надёжного извлечения.

4. **Карантин в памяти** (`quality.py`) — `_quarantine_store` не персистентен.
   Рекомендуется сохранять в БД/Redis.

5. **`UnifiedConfig`/`PipelineReport`** (`schemas.py`) — определены, но не
   используются. Либо подключить к пайплайну, либо удалить.

6. **Дублирование профилей** — `ProfileManager` (hitl.py) и `UnifiedCache`
   хранят профили независимо. Унифицировать.

### 🟢 Низкий приоритет

7. **`resources/list`** в MCP — возвращает пустой список. Реализовать ресурсы
   или убрать из capabilities.

8. **`llm_test.py`** — smoke-тест, жёстко завязан на `data/html_pages`.
   Перевести в pytest.

---

## 10. Рекомендации по настройке пакета

1. **Для реального извлечения данных** — доработать связку
   `LLMClient → AdapterState.selectors → _SelectorCollector` (п. 9.1).
2. **Для источников с антибот-защитой** — убедиться, что установлены
   `crawl4ai`, `playwright` + бинарники, и что `collectors.stealth` доступен.
3. **Для CAPTCHA-источников** — доработать HITL (п. 9.2), иначе стратегия
   не вернёт контент.
4. **Проверить конфигурацию окружения** — `LLM_*`, `POSTGRES_*`, `REDIS_*`
   (см. README.md).
5. **Запуск тестов:** `pytest tests/bp1/adaptive -v`.
