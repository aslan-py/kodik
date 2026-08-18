## 1. Настройки

- [x] 1.1 Добавить в `core/config.py` (`Settings`): `sx_org_api_key: str | None = None`, `sx_org_base_url: str = 'https://api.sx.org'`, `bp1_proxy_country: str | None = None`, `bp1_proxy_pool_size: int = 20`, `bp1_proxy_min_balance: float = 1.0`, `bp1_proxy_pool_ttl_seconds: int = 1800`, `bp1_proxy_cooldown_seconds: int = 1800`, `bp1_rpa_request_delay_seconds: float = 2.0`
- [x] 1.2 Добавить те же переменные в `.env.example` с комментариями по образцу существующего блока `--- BP-1 ---`

## 2. Вынос ротации User-Agent и задержек из `fedresurs_rpa`

- [x] 2.1 Создать `src/bp1/network/__init__.py`
- [x] 2.2 Создать `src/bp1/network/ua_rotation.py`: перенести `USER_AGENTS`, `get_random_user_agent()` из `src/bp1/collectors/fedresurs_rpa/constants.py`
- [x] 2.3 Создать `src/bp1/network/delay.py`: перенести `DEFAULT_DELAY_BETWEEN_REQUESTS`, `HUMAN_DELAY_RANGE`, `get_random_delay()`, `get_human_delay()` из `constants.py`
- [x] 2.4 В `src/bp1/collectors/fedresurs_rpa/constants.py` заменить определения на импорт из `src.bp1.network.ua_rotation`/`src.bp1.network.delay` с реэкспортом тех же имён (проверить `config.py: __all__` — список экспортируемых имён не меняется)
- [x] 2.5 Прогнать `tests/bp1/fedresurs/` — существующие тесты на `get_random_user_agent`/`get_random_delay`/`get_human_delay` проходят без изменений (проверка нулевой регрессии выноса) — 118 passed

## 3. Асинхронный провайдер прокси

- [x] 3.1 Создать `src/bp1/network/provider.py`: `SxOrgClient` на `httpx.AsyncClient` — `async def` для `get_balance`, `get_ports`, `get_port_info`, `create_port`, `search_proxies`; `format_proxy_string` (синхронная, чистая функция); `wait_for_port_ready` на `asyncio.sleep`
- [x] 3.2 Модели `ProxyPort`, `UserBalance` (dataclass/`from_dict`, как в исходном `proxy.py`)
- [x] 3.3 Обработка ошибок API (`_make_request`): экспоненциальный бэкофф на `httpx.RequestError`, поднятие `ValueError` при `success: false` в ответе — сохранить поведение исходного клиента
- [x] 3.4 Тесты `tests/bp1/network/test_provider.py` на моках `httpx.AsyncClient` (без реального обращения к `api.sx.org`): баланс, получение портов, поиск свободных прокси, ошибка API не роняет вызывающий код — 11 passed

## 4. Пул прокси и cooldown

- [x] 4.1 Создать `src/bp1/network/pool.py`: стратегия автовыбора (баланс ≥ `bp1_proxy_min_balance` → собственные порты, создать при нехватке до `bp1_proxy_pool_size`; иначе — `search_proxies`), см. `design.md` D6
- [x] 4.2 Кэш пула в Redis с TTL `bp1_proxy_pool_ttl_seconds`; ленивое обновление при обращении (без отдельной periodic-задачи, см. `design.md`)
- [x] 4.3 Собственный хелпер канонизации hostname в `network/` (не импортировать `adaptive.hostname`, см. `design.md` D1/D6) — `canonical_host()`
- [x] 4.4 Cooldown: `bp1:proxy:cooldown:{source_host}:{proxy_address}` в Redis, TTL `bp1_proxy_cooldown_seconds` — `mark_blocked()`, вызывается с consumption-стороны при отказе 401/403/429 (см. группу 6)
- [x] 4.5 `pool.acquire(source_host)` — возвращает адрес не в cooldown для данного `source_host`, либо `None`, если пул пуст/провайдер недоступен (SHALL NOT бросать исключение наружу)
- [x] 4.6 Тесты `tests/bp1/network/test_pool.py`: автовыбор по балансу, деградация при недоступном провайдере (пустой результат, не исключение), cooldown исключает адрес для источника после отказа и не влияет на другие источники — 11 passed

## 5. Троттлинг по хосту

- [x] 5.1 Создать `src/bp1/network/throttle.py`: внутрипроцессная пауза между запросами к одному hostname (`asyncio.Lock` + метки времени), минимум `bp1_rpa_request_delay_seconds`
- [x] 5.2 Тесты `tests/bp1/network/test_throttle.py`: два запроса подряд к одному хосту разделены паузой; запросы к разным хостам не блокируют друг друга (см. сценарии в `specs/bp1/rpa-network-controls/spec.md`) — 6 passed

## 6. Встраивание в `adaptive/`

- [x] 6.1 В `src/bp1/adaptive/strategies/orchestrator.py` добавить `_RPA_STRATEGIES = (StrategyType.CRAWL4AI, StrategyType.BROWSER, StrategyType.STEALTH)`
- [x] 6.2 В `AgenticOrchestrator.fetch_with_degradation` перед вызовом `strategy.fetch(url, **kwargs)` для стратегии из `_RPA_STRATEGIES`: получить прокси через `network/pool.py` (по hostname `url`), UA через `network/ua_rotation.py`, выдержать паузу через `network/throttle.py`; передать `proxy=`, `user_agent=` в kwargs (в свежей копии kwargs на каждую попытку — без утечки между стратегиями). Заодно добавлен `bind_redis()` на `AgenticOrchestrator` (прокидывает Redis-клиент в пул) и cooldown-вызов `mark_blocked()` при HTTP 401/403/429 через прокси — для этого в `StrategyResult` (`adaptive/schemas.py`) добавлено поле `http_status`
- [x] 6.3 В `src/bp1/adaptive/strategies/engines.py`: `Crawl4AIStrategy.fetch` — передать `proxy` (и `user_agent`) в `BrowserConfig` (подтверждено: `crawl4ai.BrowserConfig` принимает оба параметра как `str`)
- [x] 6.4 В `orchestrator.py`: `BrowserStrategy.fetch` — передать `proxy`/`user_agent` в `browser.new_context(proxy=..., user_agent=...)` (прокси — в `chromium.launch`, у Playwright это параметр браузера, не контекста)
- [x] 6.5 В `engines.py`: `StealthStrategy.fetch` — передать `user_agent` в `get_context_config(user_agent=...)` (сейчас не передавался вовсе — самостоятельный баг, починен тут же) и `proxy` в `p.chromium.launch(proxy=...)`
- [x] 6.6 Проверено: `_DEFAULT_USER_AGENT` в `orchestrator.py` используется только `FastStrategy`/`WaybackStrategy` (не `BROWSER`/`STEALTH`, как можно было предположить на этапе дизайна) — они вне рамки, менять нечего
- [x] 6.7 Дублирующую захардкоженную UA-строку в `src/bp1/adaptive/integration/runner/probing.py` заменена на `network/ua_rotation.get_random_user_agent()`

## 7. Встраивание в классический `fedresurs_rpa`

- [x] 7.1 В `src/bp1/adaptive/integration/runner/core.py` (`_get_parser_for_source`): получить прокси-адрес через `network/pool.py` по hostname источника, обернуть в `ProxyConfig(server=...)` (уже отформатирован пулом со схемой `http://ip:port` — учётных данных провайдер не возвращает, см. `design.md` пул._format), передать `proxy=` в `ParserFactory.get_parser(key, headless=, timeout=, proxy=)`. Метод стал `async` (был sync) — обновлён вызывающий код (`_execute_parse`) и монкипатч в `test_runner_source_aware.py`
- [x] 7.2 Проверено: `FedresursAdapter.__init__`/`FedresursRPA.default_proxy`/`BrowserManager._build_proxy_dict` принимают значение без изменений их кода
- [x] 7.3 Тесты `tests/bp1/adaptive/test_runner_proxy_wiring.py` (не `tests/bp1/fedresurs/` — прокси собирается на уровне `AdaptiveRunner._get_parser_for_source`, до входа в пакет `fedresurs_rpa`): замоканный `network/pool.py` — `ProxyConfig` собирается из полученного адреса; пустой пул → парсер без прокси, не падает; незарегистрированный источник → пул не опрашивается — 3 passed

## 8. Отказоустойчивость и наблюдаемость

- [x] 8.1 Проверено конструктивно: `ProxyPool.acquire()` и `AdaptiveRunner._get_parser_for_source()` перехватывают все свои исключения и возвращают `None`/парсер без прокси — ошибка провайдера никогда не всплывает как отказ стратегии/источника, `batch.py`-circuit-breaker её не видит
- [x] 8.2 Лог фиксирует использованный прокси на каждую попытку RPA-стратегии (`orchestrator.py`: `'Попытка стратегии %s для %s (прокси=%s)'`); добавленное поле `StrategyResult.http_status` даёт дополнительный сигнал для диагностики блокировок и используется для cooldown

## 9. Проверка сквозного сценария

- [x] 9.1 `../.venv-kodik/Scripts/python.exe -m pytest tests/bp1/ -q` — полный прогон без регрессий: 444 passed
- [x] 9.2 `../.venv-kodik/Scripts/python.exe -m ruff check src/bp1/network src/bp1/adaptive src/bp1/collectors/fedresurs_rpa` — все проверки пройдены (включая `ruff format`)
- [x] 9.3 Обновлены `src/bp1/README.md` (раздел `FedresursAdapter`) и `src/bp1/adaptive/README.md` (новый раздел «Прокси, ротация User-Agent и задержки (RPA-доступ)»)
