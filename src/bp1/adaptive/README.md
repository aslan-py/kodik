# BP-1 Adaptive — Адаптивный сбор данных

Интеллектуальная система сбора данных, которая **сама** определяет структуру
сайта, извлекает данные без предварительной настройки и адаптируется к
изменениям в реальном времени.

Пакет входит в состав **BP-1** и полностью интегрирован с его пайплайном:
реализует `BaseParser`, сохраняет результаты в `RawItem`, использует
`SearchTask` из БД и Redis для дедупликации.

---

## Быстрый старт

```bash
cd kodik

# 1. Зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, ruff и т.д.

# 2. Бинарники браузера (~150 МБ) для BROWSER/STEALTH/HITL-стратегий
python -m playwright install

# 3. Окружение (Postgres, Redis, LLM)
cp .env.example .env
#   и пропишите свои значения

# 4. Инфраструктура (Postgres + Redis)
docker compose up -d
```

> Playwright ставит только библиотеку. Сами бинарники качаются отдельной
> командой `python -m playwright install chromium`. Без них BROWSER-,
> STEALTH- и HITL-стратегии падают при старте браузера.

---

## Возможности

- **Классификация источников** — определяет тип сайта (новости, реестр, API,
  SPA), антибот-защиту, CAPTCHA, SPA-фреймворки и рекомендует стратегию.
- **Иерархия стратегий с деградацией** — при ошибке автоматически переходит к
  следующей, более «тяжёлой» стратегии: от прямого HTTP-запроса до решения
  CAPTCHA человеком (HITL).
- **Интеллектуальный парсинг** — извлекает **реальные CSS-селекторы** и схему
  данных через LLM без ручной настройки; адаптеры кэшируются в Redis.
- **Чанкирование больших страниц** — обрабатывает HTML, не помещающийся в
  контекстное окно LLM, через `HtmlCleaner → StructuredChunker → параллельное
  извлечение → ResultMerger`.
- **5 уровней контроля качества** — SCHEMA, TYPES, BUSINESS, VOLUME,
  CONSISTENCY с Quarantine-паттерном.
- **HITL для CAPTCHA** — запускает видимый браузер и детектирует момент
  решения CAPTCHA, кэширует cookies в профиль браузера.
- **Полная интеграция с BP-1** — `AdaptiveRunner` выполняет полный цикл от
  задачи до сохранения в `RawItem`.
- **Регистрация источников** — `SourceRegistrationService` по ссылке
  нормализует адрес, классифицирует сайт, добавляет `Source` в БД и
  кэширует классификацию в Redis для повторного использования.
- **Source-aware выбор поискового параметра** — для гос. источников
  (`SourceType.REGISTRY` / `SiteType.GOVERNMENT` / известные госдомены) поиск
  ведётся по ИНН, для всех остальных — **по названию конкурента**
  (`competitor.name`), т.к. на не-госсайтах ИНН не индексируется и триггер не
  является названием компании. Логика встроена в `AdaptiveRunner.run_task` через
  `SearchParamResolver`: для гос. источника берётся ИНН, для остальных —
  название конкурента (не триггер).
- **Per-source шаблоны URL поиска** — вместо жёсткого `/search?q=` каждый
  источник может иметь собственный шаблон (напр. `hh.ru ->
  /search/vacancy?text=…` — поиск по названию компании), с fallback на
  универсальный.
- **Пропуск гос. источника без ИНН** — если у конкурента нет ИНН, а источник
  ищет по ИНН, поиск не выполняется: в JSON пишется `error: not INN`. Это
  позволяет избежать бесполезной работы и некорректных данных в БД. Реализовано
  в `AdaptiveRunner.run_task` через `SearchParamResolver.missing_inn`: до парсинга
  создаётся `RawItem` со статусом `error` и сообщением `not INN`.
- **Пропуск по активности (`is_active`)** — если у конкурента или источника
  флаг `is_active = False`, поиск по задаче не выполняется, в JSON пишется
  `error: is_active=False`.

---

## Структура пакета

```
src/bp1/adaptive/
├── __init__.py              # Публичный API (реэкспорт)
├── schemas.py               # Pydantic-схемы
├── logger.py                # get_logger, new_trace_id
├── cli.py                   # CLI интерфейс
├── llm_test.py              # Smoke-тест LLM-модуля
├── requirements.txt         # Зависимости пакета
├── core/                    # Инфраструктура
│   ├── cache.py             # UnifiedCache
│   └── quality.py           # DataQualityGate
├── processing/              # Обработка HTML и извлечение данных
│   ├── html_cleaner.py      # HtmlCleaner — очистка HTML
│   ├── chunker.py           # StructuredChunker, Chunk
│   ├── merger.py            # ResultMerger — объединение результатов
│   ├── llm.py               # LLMClient, AIAgent
│   └── parser.py            # AdaptiveParser
├── strategies/              # Стратегии обхода источников
│   ├── classifier.py        # SourceClassifier
│   ├── orchestrator.py      # AgenticOrchestrator, BaseStrategy
│   ├── engines.py           # Crawl4AIStrategy, StealthStrategy, HITLStrategy
│   └── hitl.py              # HITLManager, ProfileManager
└── integration/             # Интеграция с BP-1
    ├── bridge.py            # AdaptiveBridgeParser
    ├── runner.py            # AdaptiveRunner
    └── sources.py           # SourceRegistrationService (регистрация источников)
```

Все публичные классы доступны напрямую из пакета:

```python
from src.bp1.adaptive import (
    AdaptiveParser, AdaptiveRunner, AdaptiveBridgeParser,
    SourceClassifier, SourceRegistrationService, AgenticOrchestrator,
    LLMClient, AIAgent, UnifiedCache, DataQualityGate, HITLManager,
    ProfileManager,
)
```

---

## Классификация источников

[`SourceClassifier`](strategies/classifier.py) определяет тип сайта: новостной,
реестр, API, SPA или неизвестный. Детектирует антибот-защиту (Cloudflare,
DataDome, QRATOR, Akamai, Incapsula), CAPTCHA-виджеты (reCAPTCHA, hCaptcha) и
SPA-фреймворки (React, Vue, Nuxt, Next.js, Angular).

Имеет базу известных источников (`fedresurs.ru`, `kad.arbitr.ru`,
`zakupki.gov.ru`, `nalog.ru`, `egrul.nalog.ru`, `fips.ru`), что позволяет
классифицировать их даже без скачивания страницы.

```python
import asyncio
from src.bp1.adaptive import SourceClassifier

async def main():
    classifier = SourceClassifier()

    # 1) По имени и URL (без скачивания страницы) — известные источники.
    cls = await classifier.classify(
        source_name='fedresurs.ru',
        source_url='https://fedresurs.ru/',
    )
    print(cls.source_type.value)            # 'registry'
    print(cls.recommended_strategy)         # 'STEALTH'
    print(cls.has_antibot, cls.is_spa)      # True True
    print(cls.complexity_score)             # 0.0-1.0

    # 2) По заголовкам ответа и HTML (для неизвестных сайтов).
    cls2 = await classifier.classify(
        source_name='example.com',
        source_url='https://example.com/',
        headers={'cf-ray': '...'},          # Cloudflare
        html='<html><body>...</body></html>',
    )
    print(cls2.model_dump_json(indent=2))

asyncio.run(main())
```

Результат `SourceClassification` содержит:
`source_name`, `source_type`, `complexity_score`, `has_antibot`, `has_captcha`,
`is_spa`, `recommended_strategy`.

---

## Стратегии обхода и оркестрация

[`AgenticOrchestrator`](strategies/orchestrator.py) пробует стратегии по
порядку. При ошибке или недостаточном объёме контента (меньше 300 символов)
переходит к следующей:

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

### Ручное использование оркестратора

```python
import asyncio
from src.bp1.adaptive import AgenticOrchestrator

async def main():
    orch = AgenticOrchestrator(headless=True, timeout_ms=60000)

    # Запрос с автоматической деградацией стратегий
    # (FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL).
    final = await orch.fetch_with_degradation('https://fedresurs.ru/')
    print(final.success, final.strategy.value, final.elapsed_ms)

    # Начать сразу с рекомендованной стратегии (эффективнее).
    from src.bp1.adaptive import StrategyType
    final2 = await orch.fetch_with_degradation(
        'https://kad.arbitr.ru/', start_with=StrategyType.STEALTH
    )

    # Запрос с глобальным таймаутом (с корректной очисткой ресурсов).
    timed = await orch.fetch_with_timeout(
        'https://fedresurs.ru/', timeout_ms=30000
    )
    print(timed.success, timed.error)

asyncio.run(main())
```

### Регистрация собственной стратегии

```python
from src.bp1.adaptive import AgenticOrchestrator, StrategyType
from src.bp1.adaptive.strategies.orchestrator import BaseStrategy
from src.bp1.adaptive.schemas import StrategyResult

class MyStrategy(BaseStrategy):
    strategy_type = StrategyType.CRAWL4AI  # или свой через реестр

    async def fetch(self, url: str, **kwargs) -> StrategyResult:
        # ... ваша логика
        return StrategyResult(
            strategy=self.strategy_type,
            success=True,
            data='<html>...</html>',
            content_length=1000,
        )

orch = AgenticOrchestrator()
orch.register_strategy(MyStrategy.strategy_type, MyStrategy())
```

### Прокси, ротация User-Agent и задержки (RPA-доступ)

ТЗ (`ABOUT_PROJECT/TZ.md`, BP-1) требует для источников с RPA-доступом
прокси не с корпоративных IP, ротацию User-Agent и задержки между
запросами. В адаптивном контуре это применяется только к стратегиям,
эмулирующим браузер против целевого источника — `CRAWL4AI`, `BROWSER`,
`STEALTH` (`_RPA_STRATEGIES` в [`orchestrator.py`](strategies/orchestrator.py)).
`FAST` и `WAYBACK` не затронуты: это не RPA-доступ (прямой HTTP и
обращение к archive.org, а не к целевому сайту).

Реализация — общий пакет [`src/bp1/network/`](../network/), переиспользуемый
и классическим RPA-контуром (`collectors/fedresurs_rpa/`):

- `network/provider.py` — асинхронный клиент провайдера прокси SX.org
  (`httpx.AsyncClient`): баланс, собственные порты, свободные прокси.
- `network/pool.py` — `ProxyPool`: автовыбор (баланс достаточен →
  собственные порты, создать при нехватке; иначе → свободные прокси),
  кэш пула в Redis (`bind_redis()`), cooldown адреса, заблокированного
  конкретным источником (HTTP 401/403/429 через прокси).
- `network/ua_rotation.py`, `network/delay.py` — общий пул User-Agent и
  функции случайной задержки (перенесены из
  `fedresurs_rpa/constants.py`, которая теперь их реэкспортирует).
- `network/throttle.py` — `HostThrottle`: минимальная пауза между
  последовательными запросами к одному хосту (внутрипроцессная, не
  распределённая — см. `BP1_RPA_REQUEST_DELAY_SECONDS`).

Без ключа провайдера (`SX_ORG_API_KEY` не задан) RPA-стратегии работают
как раньше — без прокси, ошибка провайдера никогда не прерывает сбор.
Настройки — блок `--- BP-1 ---` в `.env.example`
(`SX_ORG_API_KEY`, `BP1_PROXY_*`, `BP1_RPA_REQUEST_DELAY_SECONDS`).

---

## Интеллектуальный парсинг

[`AdaptiveParser`](processing/parser.py) — основной класс. Анализирует структуру
HTML (через LLM или эвристику), извлекает **реальные CSS-селекторы** и схему
данных, кэширует адаптер в Redis и переиспользует его при повторных обращениях.

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
        expected_schema={'title': str, 'url': str, 'published_at': str},
    )

    print(result.status)                  # 'ok'
    print(result.strategy_used.value)     # какая стратегия сработала
    print(len(result.items))              # количество элементов
    print(result.adapter_version)         # версия адаптера из кэша
    print(result.elapsed_ms)              # время выполнения

    # Поля каждого элемента.
    for item in result.items:
        print(item.get('title'), item.get('url'), item.get('published_at'))

asyncio.run(main())
```

Поток работы:

1. Проверка кэша адаптеров (`UnifiedCache.get_adapter`).
2. Получение HTML через оркестратор (начинает с рекомендованной стратегии из
   классификации, если она закэширована).
3. Если адаптера нет — анализ структуры через `LLMClient` → генерация
   `AdapterConfig`.
4. Сохранение адаптера в кэш.
5. Извлечение элементов по CSS-селекторам (через BeautifulSoup).
6. Валидация через `DataQualityGate`.

---

## Анализ структуры через LLM

[`LLMClient`](processing/llm.py) возвращает `AdapterConfig` с заполненными
`selectors` (CSS-селекторы для каждого поля), `expected_schema` (типы данных)
и `confidence` (уверенность 0.0–1.0).

### Простой анализ

```python
import asyncio
from src.bp1.adaptive import LLMClient

async def main():
    # Читает LLM_MODEL / LLM_BASE_URL / LLM_API_KEY из окружения или .env.
    client = LLMClient()

    html = '<html><body>...</body></html>'
    config = await client.analyze_structure(
        html=html,
        competitor='ООО АРХИТЕХ ИИ',
        expected_fields=['title', 'url', 'published_at'],
    )

    print(config.selectors)         # {'container': '...', 'title': '...', ...}
    print(config.expected_schema)   # {'title': 'str', 'url': 'str', ...}
    print(config.confidence)        # 0.87
    print(config.source_name)       # 'unknown' / имя источника

asyncio.run(main())
```

### С явными параметрами чанкирования

```python
client = LLMClient(
    max_chunk_size=8000,     # макс. размер чанка (символов)
    overlap_size=500,        # перекрытие между чанками
    max_chunks=10,           # макс. число чанков
    parallel_workers=5,      # параллельных запросов к LLM
)
```

Для страниц больше `max_chunk_size` `analyze_structure()` автоматически
вызывает чанкированный анализ. Если контент помещается в один чанк —
выполняется прямой анализ одним запросом. Иначе чанки обрабатываются
параллельно через `asyncio.gather` с ограничением параллелизма (семафор),
а результаты объединяются.

### Прямая работа с чанкированием (все этапы)

```python
import asyncio
from src.bp1.adaptive.processing.html_cleaner import HtmlCleaner
from src.bp1.adaptive.processing.llm import LLMClient
from src.bp1.adaptive.processing.merger import ResultMerger

async def main():
    html = open('page.html', encoding='utf-8').read()
    client = LLMClient()

    # 1. Очистка HTML от шума.
    cleaner = HtmlCleaner()
    cleaned = cleaner.clean(html)
    stats = cleaned['stats']
    print(f'Сжатие: x{stats["compression_ratio"]} '
          f'({stats["original_size"]} → {stats["cleaned_size"]} симв.)')

    # 2. Разбиение на логические чанки с перекрытием.
    chunks = client._chunker.chunk(cleaned)
    print(f'Чанков: {len(chunks)}')

    # 3. Параллельное извлечение через LLM.
    results = await client._extract_from_chunks(
        chunks, 'ООО АРХИТЕХ ИИ', ['title', 'url']
    )

    # 4. Объединение результатов и дедупликация.
    merger = ResultMerger()
    merged = merger.merge(
        results=results,
        chunk_metadata=[c.metadata for c in chunks],
    )
    print(merged['total_items_found'], merged['duplicate_count'])

    config = client._to_adapter_config(merged, ['title', 'url'])

asyncio.run(main())
```

### AIAgent: выбор стратегии и анализ результата

[`AIAgent`](processing/llm.py) принимает решения: выбирает стратегию обхода по
классификации и анализирует результаты парсинга, возвращая рекомендацию по
доработке адаптера.

```python
import asyncio
from src.bp1.adaptive import AIAgent, SourceClassifier

async def main():
    agent = AIAgent()

    cls = await SourceClassifier().classify(
        source_name='lenta.ru', source_url='https://lenta.ru/'
    )

    # Выбор стратегии через LLM.
    strategy = await agent.choose_strategy(cls)
    print(strategy.value)

    # Анализ результата парсинга — рекомендация по доработке.
    recommendation = await agent.analyze_result(
        html='<html>...</html>',
        items=[{'title': 'Запись', 'url': 'https://example.com/1'}],
        source_name='lenta.ru',
    )
    print(recommendation['recommendation'])
    print(recommendation['confidence'])

asyncio.run(main())
```

> **Эвристический fallback:** если `LLM_API_KEY` / `OPENAI_API_KEY` не заданы,
> пакет автоматически переключается на эвристический анализ HTML по тегам и
> выбор стратегии по классификации. Пакет остаётся полностью работоспособным
> без внешних LLM-сервисов.

---

## Source-aware поисковый параметр и шаблоны URL

Для каждого источника адаптивный сбор выбирает **правильный поисковый параметр**
и **шаблон URL поиска**:

- [`SearchParamResolver`](integration/sources.py) определяет, искать ли по **ИНН**
  или по **названию конкурента**. Гос. источники (`SourceType.REGISTRY`,
  `SiteType.GOVERNMENT`, известные госдомены) → ИНН; остальные → **название
  конкурента** (`competitor.name`), т.к. на не-госсайтах ИНН не индексируется и
  триггер не является названием компании (напр. поиск по "Москва" не находит
  вакансии ООО "АРХИТЕХ ИИ").
- [`SearchUrlTemplateRegistry`](integration/sources.py) выбирает per-source шаблон
  URL (напр. `hh.ru -> /search/vacancy?text=…` — поиск по названию компании),
  с fallback на универсальный `/search?q=`.
- **Пропуск гос. источника без ИНН** — метод `SearchParamResolver.missing_inn()`
  определяет, что источнику нужен ИНН, а у конкурента его нет. В этом случае
  поиск не выполняется: в JSON фиксируется `error: not INN`, избегая лишней
  работы и попадания некорректных данных в БД.

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

# На не-гос. источнике поиск идёт по названию конкурента (competitor.name),
# а не по триггеру.
param = resolver.resolve(
    'hh.ru', competitor_inn=None, competitor='ООО АРХИТЕХ ИИ', trigger='Москва'
)
print(param)  # 'ООО АРХИТЕХ ИИ'

# Построение URL с per-source шаблоном (название без кавычек).
registry = SearchUrlTemplateRegistry()
print(registry.build_url('hh.ru', 'ООО АРХИТЕХ ИИ'))
# https://hh.ru/search/vacancy?text=%D0%9E%D0%9E%D0%9E+%D0%90%D0%A0%D0%A5%D0%98%D0%A2%D0%95%D0%A5+%D0%98%D0%98
```

---

## Регистрация источников

[`SourceRegistrationService`](integration/sources.py) позволяет добавить новый
источник по ссылке без ручной настройки. По URL выполняет цепочку:

1. **Нормализация** — выделяет основную часть адреса (`scheme://hostname/`):
   `https://www.lenta.ru/news/...` → `https://lenta.ru/`.
2. **Классификация** — через `SourceClassifier` определяет тип сайта и
   рекомендованную стратегию.
3. **Запись в БД** — создаёт `Source(name='https://lenta.ru/')`, только если
   такого источника ещё нет (идемпотентность).
4. **Кэширование** — классификация сохраняется в Redis
   (`bp1:classification:{hostname}`, TTL 7 дней) для повторного использования.

```python
import asyncio

from core.database import AsyncSessionLocal
from core.redis_client import get_redis
from src.bp1.adaptive import SourceRegistrationService

async def main():
    redis = await get_redis()
    try:
        async with AsyncSessionLocal() as session:
            service = SourceRegistrationService(session, redis_client=redis)
            result = await service.register('https://www.lenta.ru/news')
            await session.commit()

            print(result.source_name)          # 'https://lenta.ru/'
            print(result.host)                 # 'lenta.ru'
            print(result.created)              # True (False, если уже был)
            print(result.classification.source_type.value)  # 'news'
            print(result.classification.recommended_strategy)  # 'FAST'
    finally:
        await redis.aclose()

asyncio.run(main())
```

> Формат `Source.name` — **полный URL** (как в БД/`source.csv`). `AdaptiveRunner`
> сам извлекает hostname при построении поискового URL, поэтому источник
> корректно обрабатывается универсальным адаптивным парсером.

---

## Контроль качества

[`DataQualityGate`](core/quality.py) — пятиуровневая валидация с
Quarantine-паттерном:

| Уровень | Метод | Проверка |
|---------|-------|----------|
| 1. `SCHEMA` | `validate_schema` | Обязательные поля (`url`, `title`) |
| 2. `TYPES` | `validate_types` | Типы данных |
| 3. `BUSINESS` | `validate_business_rules` | Бизнес-правила (мин. длина и т.д.) |
| 4. `VOLUME` | `validate_volume` | Мониторинг объёма (аларм при падении > 20%) |
| 5. `CONSISTENCY` | `validate_consistency` | Дубликаты |

```python
from src.bp1.adaptive import DataQualityGate

gate = DataQualityGate(
    source_name='lenta.ru',
    quarantine_dir='./quarantine',   # сохранять карантин на диск (опционально)
)

data = {
    'items': [
        {'url': 'https://example.com/1', 'title': 'Запись 1'},
        {'url': 'https://example.com/2', 'title': ''},  # нет title
        {'url': 'https://example.com/1', 'title': 'Запись 1'},  # дубль
    ]
}

report = gate.validate_schema(data)
print(report.passed, report.errors)          # False, ['missing required field "title"']

report_all = gate.validate_all(data)
for r in report_all:
    print(r.level.value, r.passed, r.passed_count, r.quarantined_count)

# Проблемные записи помещаются в карантин.
print(gate.quarantined)   # [QuarantineRecord, ...]
```

---

## HITL для CAPTCHA

[`HITLManager`](strategies/hitl.py) запускает видимый браузер и **детектирует
момент решения CAPTCHA** (по изменению URL, появлению новых cookies или
исчезновению CAPTCHA-виджета из DOM) вместо фиксированного ожидания. После
решения возвращает cookies **и HTML страницы**. Результат (cookies) кэшируется
в профиль браузера на диске и переиспользуется при следующих обращениях.

```python
import asyncio
from src.bp1.adaptive import HITLManager

async def main():
    # Запускает видимый браузер (headless=False внутри).
    manager = HITLManager(profiles_dir='./src/bp1/data/profiles')

    # Обработать CAPTCHA: если профиль уже есть — вернётся сразу без человека,
    # иначе открывается видимый браузер и ожидается решение человеком.
    response = await manager.handle_challenge(
        url='https://site-with-captcha.ru/',
        source_name='site-with-captcha.ru',
        challenge_type='captcha',
        timeout_s=120,          # макс. время ожидания решения
        poll_interval_s=2.0,    # интервал опроса состояния страницы
    )
    print(response.success, response.profile_id)
    print(bool(response.cookies))   # cookies после решения (кэшируются в профиль)
    print(bool(response.html))      # HTML страницы после решения

    # Ручное разрешение запроса (если решение получено внешне).
    # manager.resolve(request_id, cookies={...})

asyncio.run(main())
```

---

## Кэширование

[`UnifiedCache`](core/cache.py) хранит:

- **Адаптеры** — Redis, TTL 7 дней.
- **Классификации источников** — Redis, TTL 7 дней.
- **Профили браузеров** — диск (`cache_dir/profiles`).
- **HTML-снапшоты** — диск (`cache_dir/snapshots`).

```python
import asyncio
from src.bp1.adaptive import UnifiedCache

async def main():
    cache = UnifiedCache()

    # Получить адаптер источника из кэша.
    adapter = await cache.get_adapter('lenta.ru')
    if adapter is not None:
        print(adapter.selectors, adapter.confidence)

    # Очистить адаптер.
    await cache.clear_adapter('lenta.ru')

    # Профиль браузера для HITL.
    profile = await cache.get_profile('lenta.ru')
    print(profile)

asyncio.run(main())
```

---

## Полная интеграция с BP-1: AdaptiveRunner

[`AdaptiveRunner`](integration/runner.py) — единая точка входа. Выполняет полный
цикл: получение задачи из БД → классификация источника → парсинг (с
возможностью использования специализированных RPA-парсеров для известных
источников) → валидация → сохранение в `RawItem` → сохранение HTML/JSON на диск
→ обновление Redis (дедупликация).

```python
import asyncio
from src.bp1.adaptive import AdaptiveRunner
from core.database import AsyncSessionLocal
from core.redis_client import get_redis

async def main():
    runner = AdaptiveRunner(
        mode='adaptive',      # adaptive | hybrid | fallback
        headless=True,
        timeout=60000,
        quality_gate_enabled=True,
        cache_profiles=True,
        max_concurrent=5,
    )

    redis = await get_redis()
    try:
        async with AsyncSessionLocal() as session:
            # Одна задача по ID.
            result = await runner.run_task(task_id=40, session=session, redis=redis)
            print(result.status, result.total_duration_ms)

            # Все активные задачи.
            # results = await runner.run_all(session=session, redis=redis)
    finally:
        await redis.aclose()

asyncio.run(main())
```

### Режимы работы

| Режим | Описание |
|-------|----------|
| `adaptive` | Только адаптивный парсинг |
| `hybrid` | Адаптивный + legacy fallback |
| `fallback` | adaptive → legacy → browser → wayback → HITL |

---

## Интеграция с ParserFactory

[`AdaptiveBridgeParser`](integration/bridge.py) реализует `BaseParser` из BP-1 и
конвертирует результат `AdaptiveParser` в `ParsedResponse`.

```python
from src.bp1.adaptive import AdaptiveBridgeParser
from src.bp1.base_parser import ParserFactory

# Регистрация универсального адаптивного парсера.
ParserFactory.register('adaptive', AdaptiveBridgeParser)

# Регистрация для конкретного источника.
ParserFactory.register('lenta.ru', lambda: AdaptiveBridgeParser(
    source_name='lenta.ru'
))

# Использование как обычного BaseParser.
parser = AdaptiveBridgeParser(source_name='lenta.ru')
resp = await parser.parse(
    url='https://lenta.ru/search?q=ИИ',
    search_task_id=40,
    competitor='ООО АРХИТЕХ ИИ',
    trigger='ИИ',
)
print(resp.items[0].title, resp.items[0].url)
```

---

## CLI

Собственного CLI у адаптивного контура больше нет: он объединён с CLI
этапа — `python -m src.bp1.cli` (см. [../README.md](../README.md)).
Команды сбора — обёртки над заданиями [`../jobs.py`](../jobs.py).

```bash
# Категоризация источника без записи в БД
python -m src.bp1.cli classify lenta.ru

# Сбор: по источнику / по конкуренту / всё
python -m src.bp1.cli source lenta.ru
python -m src.bp1.cli competitor "ООО АРХИТЕХ ИИ"
python -m src.bp1.cli all

# Видимый браузер (для отладки HITL/STEALTH)
python -m src.bp1.cli source lenta.ru --no-headless

# Управление кэшем адаптеров
python -m src.bp1.cli cache --show lenta.ru
python -m src.bp1.cli cache --clear lenta.ru

# Отчёт качества по задаче
python -m src.bp1.cli quality --task-id 40
```

Команды `profile` и режимы `--mode hybrid --fallback` в объединённый CLI
не переносились: профили HITL правятся на диске
(`src/bp1/data/profiles/`), а режим прогона задаётся настройкой
`BP1_ADAPTIVE_MODE` — флаг в CLI дублировал её и расходился с прогоном
через конвейер.

---

## Smoke-тест LLM

`llm_test.py` демонстрирует все функции LLM-модуля на реальной HTML-странице
из `data/html_pages`:

1. `SourceClassifier.classify` — классификация источника.
2. `LLMClient.analyze_structure` — полный анализ (с авто-чанкированием).
3. `LLMClient.analyze_structure_chunked` — явное чанкирование по этапам.
4. `LLMClient._llm_analyze` — прямой анализ одним запросом.
5. `AIAgent.choose_strategy` — выбор стратегии через LLM.
6. `AIAgent.analyze_result` — анализ результата парсинга.

```bash
python -m src.bp1.adaptive.llm_test
```

> Перед запуском пропишите реальный `LLM_API_KEY` в константе в начале файла
> `llm_test.py`, либо задайте `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` в
> окружении или `.env`.

---

## Настройка LLM

Пакет использует LLM для анализа структуры HTML и выбора стратегии обхода.
Провайдер настраивается через переменные окружения (автоматически загружаются
из `.env` при импорте `llm.py` через `setdefault`, не перезаписывая уже
заданные значения):

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

Пример для OpenAI-совместимого API (например, DeepSeek):

```dotenv
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-...
```

---

## Запуск тестов

Тесты пакета находятся в `kodik/tests/bp1/adaptive/`. Нужны `pytest` и
`pytest-asyncio` (уже в `requirements-dev.txt`).

```bash
# Все тесты пакета
pytest tests/bp1/adaptive -v

# Отдельный файл
pytest tests/bp1/adaptive/test_classifier.py -v
pytest tests/bp1/adaptive/test_llm.py -v
pytest tests/bp1/adaptive/test_chunking.py -v   # HtmlCleaner, Chunker, Merger
pytest tests/bp1/adaptive/test_orchestrator.py -v
pytest tests/bp1/adaptive/test_engines.py -v
pytest tests/bp1/adaptive/test_quality.py -v
pytest tests/bp1/adaptive/test_parser.py -v
pytest tests/bp1/adaptive/test_hitl.py -v
pytest tests/bp1/adaptive/test_integration.py -v
pytest tests/bp1/adaptive/test_source_registration.py -v   # регистрация источников

# Все тесты проекта
pytest -v
```

### Линтер и форматтер

```bash
ruff check src/bp1/adaptive tests/bp1/adaptive
ruff format --check src/bp1/adaptive tests/bp1/adaptive
```

---

## Зависимости

Полный список — в [`requirements.txt`](requirements.txt):

- `pydantic>=2.0` — Pydantic-схемы.
- `crawl4ai>=0.4.0` — AI-краулинг (CRAWL4AI-стратегия).
- `openai>=1.0.0` — LLM-клиент (`AsyncOpenAI`).
- `playwright>=1.40` — браузерная автоматизация (BROWSER/STEALTH/HITL).
- `sqlalchemy>=2.0` — AsyncSession (runner, cli).

Внутренние модули репозитория, от которых зависит пакет:
`src.bp1.base_parser`, `src.bp1.tasks`, `src.bp1.models`,
`src.bp1.constants`, `src.bp1.parsers`, `src.bp1.collectors.stealth`,
`core.config`, `core.database`, `core.redis_client`.

---

## Логирование

Пакет использует стандартный модуль `logging`. Каждый модуль получает логгер
через `logging.getLogger(__name__)`. [`logger.py`](logger.py) предоставляет
тонкую обёртку `get_logger()` и утилиту `new_trace_id()` и **не создаёт
хендлеры** — конфигурация (`basicConfig`) выполняется в точке входа
(cli.py, runner.py и т.д.), чтобы избежать дублирования сообщений.

```python
from src.bp1.adaptive import get_logger
from src.bp1.adaptive.logger import new_trace_id

logger = get_logger('my_module')
trace_id = new_trace_id()   # uuid hex для трассировки
logger.info('Начало сбора %s', trace_id)
