## 1. `network/provider.py` — не ретраить аутентификационные ошибки

- [x] 1.1 В `_make_request`: перед веткой ретрая проверить статус ответа — при 401/403 сразу `raise` без ретрая; остальные `httpx.HTTPError` (5xx, 429, сетевые/таймаут) ретраятся как раньше
- [x] 1.2 Тест: 401/403 — `_make_request` бросает исключение с первой попытки, `asyncio.sleep` не вызывается, повторного запроса нет
- [x] 1.3 Тест: существующее поведение (5xx/сетевая ошибка — 3 ретрая с бэкоффом) не сломано — уже было покрыто `TestRetryOnHttpError`, прогнано заново, зелёное

## 2. `network/pool.py` — маркер «провайдер недоступен» и проверка

- [x] 2.1 Redis-ключ `bp1:proxy:provider_down` (без привязки к источнику — общий для всего провайдера)
- [x] 2.2 Метод проверки провайдера `check_health()`: если `api_key` не задан — no-op, успех; иначе один дешёвый авторизованный вызов (`get_balance()`); при ошибке — выставить маркер в Redis (TTL переиспользует `bp1_proxy_pool_ttl_seconds` — новой настройки не заводилось), при успехе — снять маркер
- [x] 2.3 `_get_pool()`: если маркер выставлен — сразу вернуть `[]`, не вызывая `_select_pool()`
- [x] 2.4 Лог: одно сообщение на вызов `check_health()` (метод и так вызывается один раз за прогон — см. группу 3), с пометкой о будущей интеграции `core.mail.send_email(to=settings.test_email, ...)`/`core.telegram.send_telegram(chat_id=settings.test_tg, ...)` (заглушка, не вызывается, см. `design.md` D3)
- [x] 2.5 Тесты `tests/bp1/network/test_pool.py` (`TestCheckHealth`, 5 тестов): рабочий провайдер не выставляет маркер; сломанный — выставляет маркер и логирует один раз; выставленный маркер снимается при восстановлении; `acquire()` при маркере не обращается к провайдеру повторно; без `api_key` — no-op, успех — 16/16 passed

## 3. Встраивание в `AdaptiveRunner.run_all`

- [x] 3.1 В `batch.py::run_all`: явно вызван `self._bind_redis(redis_client)` (раньше вызывался только внутри `run_task` на каждую задачу, не один раз в начале) и сразу за ним `await self._proxy_pool.check_health()`, до диспетчеризации задач
- [x] 3.2 Тесты `tests/bp1/adaptive/test_runner_concurrency.py` (2 новых): `check_health()` вызывается ровно один раз, первым, до `run_task`; `check_health() -> False` не прерывает `run_all` — задачи выполняются как обычно. Заодно исправлен риск регрессии: `_make_runner` во всех существующих тестах конкурентности теперь мокает `check_health()` — без мока `run_all` бил бы в реальный `api.sx.org` (в `.env` уже настоящий `SX_ORG_API_KEY`) — 8/8 passed

## 4. Проверка

- [x] 4.1 `../.venv-kodik/Scripts/python.exe -m pytest tests/bp1/ -q` — без регрессий: 453 passed
- [x] 4.2 `../.venv-kodik/Scripts/python.exe -m ruff check src/bp1/network src/bp1/adaptive tests/bp1/network tests/bp1/adaptive` — чисто
- [x] 4.3 Обновлён `src/bp1/adaptive/README.md` — новый абзац «Проверка провайдера в начале прогона» в разделе «Прокси, ротация User-Agent и задержки»

## 5. Находки реального прогона (`python -m src.bp1.cli all`, 3 попытки)

По запросу — 3 попытки реального прогона против настоящего провайдера
(`SX_ORG_API_KEY`, баланс 0.0). Попытки 1 и 2 вскрыли реальные баги,
не видимые на моках; попытка 3 — чистая. Все правки — в рамках той же
цели change (circuit breaker реально работает), не расширение объёма.

- [x] 5.1 **Ретрай не только 401/403, а любой 4xx кроме 429**: реальный
  провайдер отдаёт HTTP 400 `{"success": false, "message": "Insufficient
  funds on the balance sheet"}` на `/v2/proxy/search` при балансе ниже
  порога — это тоже детерминированный отказ, ретраить бессмысленно, как и
  401/403. `provider.py::_make_request` — условие пропуска ретрая
  обобщено с `status in (401, 403)` на `400 <= status < 500 and status !=
  429`. Тесты `TestNoRetryOn4xx` (обобщены из `TestNoRetryOnAuthError`,
  параметризованы по 400/401/403/404) + `test_429_still_retries`
- [x] 5.2 **`check_health()` проверял только `get_balance()`, не реальный
  путь отбора**: с реальным ключом баланс читается успешно (200 OK), но
  сама ветка `search_proxies()` (баланс ниже порога) отдельно отказывает
  — проверка одного баланса такой отказ не ловила, circuit breaker не
  срабатывал на попытке 1. `check_health()` переписан на вызов
  `self._select_pool()` (та же стратегия автовыбора, что и у
  `acquire()`) вместо прямого `client.get_balance()` — заодно на успехе
  сразу прогревает кэш пула в Redis. Тест
  `test_search_proxies_failure_marks_unhealthy` +
  `test_healthy_check_pre_warms_pool_cache`
- [x] 5.3 **`AdaptiveParser.bind_redis()` не пробрасывал Redis в
  `AgenticOrchestrator._proxy_pool`** — привязывал только `self._cache.
  redis`. Из-за этого на попытке 2 маркер `bp1:proxy:provider_down`,
  выставленный `check_health()` в `AdaptiveRunner._proxy_pool`, не был
  виден пулу оркестратора (отдельный экземпляр `ProxyPool`) — RPA-стратегии
  (`BROWSER`/`STEALTH`/`CRAWL4AI`) продолжали бить в провайдера на каждый
  `acquire()`, несмотря на уже сработавший circuit breaker. Добавлен
  вызов `self._orchestrator.bind_redis(redis_client)` внутри
  `AdaptiveParser.bind_redis()`. Тест
  `test_bind_redis_cascades_to_orchestrator_proxy_pool`
  (`tests/bp1/adaptive/test_parser.py`)
- [x] 5.4 **`ProxyPool(api_key=None)` не отличим от «параметр не
  передан»** — оба падали на `settings.sx_org_api_key` (реальный ключ),
  из-за чего тест `TestDegradation.test_no_api_key_returns_none` (и любой
  тест с явным `api_key=None`) молча бил в реальную сеть, если в `.env`
  задан `SX_ORG_API_KEY` (задан с прошлого change). Сентинел `_UNSET`
  вместо `None` по умолчанию в `ProxyPool.__init__` — отличает «не
  передано» (взять из settings) от «явно передано `None`» (ключа нет).
  Существующие тесты прошли без изменений после фикса
- [x] 5.5 Итоговая проверка: `pytest tests/bp1/adaptive/ tests/bp1/network/
  tests/bp1/fedresurs/ -q` — 404 passed; 3 реальных прогона `python -m
  src.bp1.cli all` — везде exit 0, 3/3 задачи, 100% успех; попытка 3
  (после 5.1–5.4) — ровно один запрос к провайдеру за весь прогон, далее
  ни одного повторного обращения
