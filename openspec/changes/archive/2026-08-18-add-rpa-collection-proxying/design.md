## Context

См. `proposal.md` — Why/What Changes. Технический контекст, важный для
решений ниже:

- Конвейер асинхронный (`async def fetch`, Playwright async API); в
  проекте уже есть `httpx>=0.27` (используется BP-6 `ai_assistant.py`) —
  синхронный `requests`-клиент провайдера портить асинхронность не должен.
- `src/bp1/` — плоская раскладка сиблингов: `adaptive/`, `collectors/`
  (внутри — `fedresurs_rpa/`, `stealth/`), `parsers/`. Ни один RPA-контур
  не должен зависеть от другого (`adaptive` не импортирует
  `collectors.fedresurs_rpa` и наоборот) — общая инфраструктура нужна на
  их общем уровне, `src/bp1/`.
- `fedresurs_rpa/constants.py` уже содержит рабочий пул
  `USER_AGENTS`/`get_random_user_agent()` и
  `get_random_delay()`/`get_human_delay()`, используемые в `browser.py` и
  `parser.py`. Их нужно вынести и переиспользовать, а не переписывать.
- `AgenticOrchestrator` (`adaptive/strategies/orchestrator.py`) уже
  централизует выбор стратегии по классификации источника
  (`_ALLOWED_STRATEGIES_TABLE`) — естественное место для ещё одного
  решения «эта стратегия — RPA, применить сетевые правила».
- `UnifiedCache` (`adaptive/core/cache.py`) — образец Redis-кэша с
  каноническим hostname-ключом и TTL из настроек `BP1_*_TTL_SECONDS`.
  Пул прокси и cooldown «сгоревших» адресов используют тот же приём, но
  не сам класс `UnifiedCache` — он живёт в `adaptive/`, а нужен и
  `collectors/fedresurs_rpa/`.
- `settings.celery_bp1_worker_concurrency = 1` по умолчанию (BP-1 с
  браузером — один воркер-процесс). Это допущение важно для решения по
  троттлингу ниже.

## Goals / Non-Goals

**Goals:**
- Прокси, ротация User-Agent и задержки между запросами — для RPA-стратегий
  обоих контуров (`adaptive/`: `BROWSER`, `STEALTH`, `CRAWL4AI`;
  классический `fedresurs_rpa`).
- Провайдер прокси — асинхронный клиент (`httpx.AsyncClient`), не
  блокирующий event loop.
- Деградация при недоступности провайдера/пустом пуле — прогон
  продолжается без прокси, а не падает.
- Общий пул User-Agent/задержек — одно место истины для обоих контуров.

**Non-Goals:**
- Не переписывается уже работающий цикл ретраев/бэкоффа в
  `fedresurs_rpa/parser.py` — только источник UA/задержек меняется на
  общий, сама логика вызова остаётся.
- Не вводится распределённый (Redis-based) троттлинг между процессами —
  при `celery_bp1_worker_concurrency=1` внутрипроцессный асинхронный
  троттлинг достаточен (см. риски).
- Не покрывается `FAST`/`WAYBACK` — не RPA-доступ по определению ТЗ.
- Не реализуется управление шаблонами прокси (`ProxyTemplate` в
  `proxy.py`) — в текущих сценариях не используется, лишняя поверхность.
- Не меняется структура `SearchRequest`/`ProxyConfig` в
  `fedresurs_rpa/schemas.py` — она уже готова, только заполняется.

## Decisions

### D1 — Новый пакет `src/bp1/network/`, общий для обоих контуров
Модули: `provider.py` (асинхронный клиент SX.org), `pool.py` (менеджер
пула прокси + cooldown), `ua_rotation.py` (перенесённые
`USER_AGENTS`/`get_random_user_agent`), `delay.py` (перенесённые
`get_random_delay`/`get_human_delay`/`DEFAULT_DELAY_BETWEEN_REQUESTS`/
`HUMAN_DELAY_RANGE`), `throttle.py` (пауза между запросами к одному
хосту — новое, в `fedresurs_rpa` такого троттлинга по хосту не было,
только между конкретными шагами одного сценария).

`fedresurs_rpa/constants.py` заменяет собственные определения на
`from src.bp1.network.ua_rotation import USER_AGENTS, get_random_user_agent`
и аналогично для задержек, сохраняя реэкспорт тех же имён — код,
вызывающий `get_random_user_agent()`/`get_random_delay()` в
`browser.py`/`parser.py`, не меняется.

**Альтернатива (отклонена):** положить общий код в `adaptive/`, а
`fedresurs_rpa` — импортировать из `adaptive`. Отклонено: `fedresurs_rpa`
не должен знать про `adaptive` — это два независимых контура одного
уровня, зависимость в одну сторону создаёт связанность без причины.

### D2 — Провайдер: асинхронный порт `SxOrgClient` на `httpx.AsyncClient`
Прямой перевод предоставленного `SxOrgClient`: `requests.Session` →
`httpx.AsyncClient`, все методы — `async def`, `time.sleep` в
`wait_for_port_ready` → `asyncio.sleep`. Переносятся методы, реально
нужные для стратегии автовыбора: `get_balance`, `get_ports`,
`create_port`, `wait_for_port_ready`, `search_proxies`,
`format_proxy_string`. Управление шаблонами (`get_templates`,
`create_template` и т.д.) и справочники (`get_cities`, `get_asns`) не
переносятся — нет сценария использования (см. Non-Goals).

**Альтернатива (отклонена):** обернуть исходный `requests`-клиент в
`asyncio.to_thread`, как `_fetch_sync` в `orchestrator.py`. Отклонено:
`httpx` уже есть в зависимостях и даёт нативный асинхронный клиент без
накладных расходов на пул потоков — оборачивать в поток то, что не
обязано быть синхронным, не нужно.

### D3 — Стратегия выбора прокси: без условия по классификации источника
Прокси применяется ко всем запросам RPA-стратегий безусловно (когда пул
не пуст), а не только при `classification.has_antibot`. ТЗ формулирует
требование на уровне типа доступа источника («источники с RPA-доступом»),
а не на уровне отдельного запроса — RPA-стратегия сама по себе уже
означает «этот источник требует эмуляции браузера», доп. условие поверх
классификации добавило бы ещую ось ветвления в и без того сложную
`_ALLOWED_STRATEGIES_TABLE` без ценности, которую просит ТЗ.

### D4 — Точка встраивания: `AgenticOrchestrator`, не отдельные `Strategy`
Новый кортеж `_RPA_STRATEGIES = (CRAWL4AI, BROWSER, STEALTH)` в
`orchestrator.py` (отдельный от `_JS_RENDERING_STRATEGIES` — тот служит
другой цели, проверке информативности контента, и не включает
`CRAWL4AI`). Перед вызовом `strategy.fetch(url, **kwargs)` для стратегии
из `_RPA_STRATEGIES` оркестратор:
1. запрашивает прокси-адрес и User-Agent у `network/pool.py` +
   `network/ua_rotation.py`;
2. выдерживает паузу через `network/throttle.py` (по hostname из `url`);
3. передаёт `proxy=`, `user_agent=` в `kwargs` стратегии.

Каждая `Strategy.fetch()` принимает `proxy: str | None` и
`user_agent: str | None` через `**kwargs` и передаёт их в
Playwright (`browser.new_context(proxy=..., user_agent=...)`) или
`crawl4ai.BrowserConfig(proxy_config=...)`.

**Альтернатива (отклонена):** каждая `Strategy` сама обращается к
`network/`. Отклонено: решение «эта стратегия — RPA» уже принадлежит
оркестратору (он же решает допустимое подмножество стратегий по
классификации) — дублировать эту классификацию внутри каждого класса
стратегии избыточно и рискует разойтись.

### D5 — `fedresurs_rpa`: заполнить существующий `ProxyConfig`, не менять форму
`_get_parser_for_source` (`adaptive/integration/runner/core.py`) получает
прокси/UA из того же `network/pool.py`/`network/ua_rotation.py`, что и
`adaptive`-стратегии, оборачивает адрес в уже существующий
`ProxyConfig(server=..., username=..., password=...)` и передаёт
`proxy=` в `ParserFactory.get_parser(key, headless=, timeout=, proxy=)`.
`FedresursAdapter.__init__`, `SearchRequest.proxy`, `BrowserManager.
_build_proxy_dict` не меняются — они уже рассчитаны на это.

### D6 — Хранение пула и cooldown: Redis, канонический hostname-ключ
`network/pool.py` хранит в Redis: (а) кэш последнего полученного от
провайдера пула адресов с TTL (новая настройка,
`bp1_proxy_pool_ttl_seconds`, по аналогии с `BP1_ADAPTER_TTL_SECONDS` и
остальными `BP1_*_TTL_SECONDS`); (б) cooldown-ключ вида
`bp1:proxy:cooldown:{source_host}:{proxy_address}` с TTL
`bp1_proxy_cooldown_seconds`, выставляемый при отказе, похожем на
блокировку по IP (статус 401/403/429 при установлении соединения через
прокси). hostname источника приводится тем же способом, что и в
`UnifiedCache._canonical_source_name` (не через импорt из `adaptive`, а
собственным маленьким хелпером в `network/` — см. D1: `network/` не
зависит от `adaptive/`).

### D7 — Троттлинг: внутрипроцессный, по hostname, не распределённый
`network/throttle.py` — `dict[str, float]` (последняя метка времени
запроса по hostname) с `asyncio.Lock` на запись, в памяти процесса.
Основание — Non-Goals/Context: `celery_bp1_worker_concurrency=1` по
умолчанию, распределённый троттлинг через Redis добавил бы сложность без
текущей необходимости (см. риск ниже, если допущение изменится).

### D8 — Настройки (`core/config.py`, `.env.example`), паттерн `BP1_*`
Опциональны, при отсутствии ключа провайдера RPA-стратегии работают без
прокси (деградация из D-требования «Отказ провайдера прокси не
останавливает сбор»):

```
SX_ORG_API_KEY=                        # ключ провайдера прокси, опционален
SX_ORG_BASE_URL=https://api.sx.org
BP1_PROXY_COUNTRY=                     # код страны для пула, пусто = без фильтра
BP1_PROXY_POOL_SIZE=20
BP1_PROXY_MIN_BALANCE=1.0              # порог баланса: свои порты vs свободные прокси
BP1_PROXY_POOL_TTL_SECONDS=1800
BP1_PROXY_COOLDOWN_SECONDS=1800
BP1_RPA_REQUEST_DELAY_SECONDS=2.0      # минимальная пауза между запросами к одному хосту
```

## Risks / Trade-offs

- **[Риск]** Провайдер тарифицирует по балансу (`create_port` расходует
  средства) → **Митигация**: `min_balance_to_create` (как в исходном
  `ProxyStrategy`) — создание новых портов только при достаточном
  балансе, иначе используются бесплатные `search_proxies`.
- **[Риск]** Внутрипроцессный троттлинг (D7) перестанет работать корректно,
  если `celery_bp1_worker_concurrency` увеличат >1 (несколько процессов
  независимо друг от друга будут слать запросы к одному хосту без общей
  паузы) → **Митигация**: явно задокументировано здесь и в коде
  `throttle.py`; при повышении concurrency потребуется вынести троттлинг
  на Redis (отдельное изменение, не в рамках этого).
- **[Риск]** Детекция «отказ похож на блокировку по IP» (для cooldown,
  D6) — эвристика по коду ответа (401/403/429), может дать
  ложноположительный cooldown на временном сетевом сбое →
  **Митигация**: короткий TTL cooldown (по умолчанию 30 минут,
  настраивается), не постоянная блокировка адреса.
- **[Риск]** Прямой перевод `SxOrgClient` на `httpx.AsyncClient` без
  доступа к реальному API для тестирования (только пример-клиент) →
  **Митигация**: контрактные тесты на моках `httpx.AsyncClient`
  (мокаем `_make_request`), без интеграционных тестов против реального
  `api.sx.org`.

## Migration Plan

1. Вынести UA/delay-код из `fedresurs_rpa/constants.py` в
   `network/ua_rotation.py`/`network/delay.py`; `constants.py` реэкспортирует
   — нулевой риск регрессии для существующих вызывающих мест.
2. Добавить `network/provider.py` (`SxOrgClient` асинхронный) + тесты на
   моках.
3. Добавить `network/pool.py` (стратегия автовыбора + Redis-кэш +
   cooldown) + `network/throttle.py`.
4. Добавить настройки в `core/config.py`/`.env.example` (опциональны —
   безопасно мёржить отдельно от остального).
5. Встроить в `AgenticOrchestrator`/`engines.py` (`adaptive/`) —
   `_RPA_STRATEGIES`, вызовы `network/` перед `strategy.fetch(...)`.
6. Встроить в `_get_parser_for_source` (`fedresurs_rpa`) —
   заполнить `ProxyConfig` реальным значением.
7. Откат — на любом шаге: настройки опциональны, `SX_ORG_API_KEY` не
   задан ⇒ пул всегда пуст ⇒ поведение как до изменения (прямые запросы),
   без флага фичи.

## Open Questions

- Нужен ли `HITL` в `_RPA_STRATEGIES`? Формально это тоже эмуляция
  пользователя, но там уже участвует живой человек — прокси может
  разорвать непрерывность его сессии/cookies. Не блокирует реализацию:
  по умолчанию `HITL` в `_RPA_STRATEGIES` не входит, при необходимости
  добавляется отдельным изменением после проверки на практике.
