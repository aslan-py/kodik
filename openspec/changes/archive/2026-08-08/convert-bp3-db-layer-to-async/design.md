## Context

`BaseModule.process(self, ctx: ProjectContext) -> ProjectContext` — синхронный метод, `Pipeline.run()` вызывает модули друг за другом синхронно, без `await`. `run_bp3()` (`src/bp3/pipeline.py`) объявлен как `async def` только ради единого контракта с `run_bp2`/`run_bp4`/`run_bp5` — внутри он не await'ит ничего, просто зовёт `pipeline.run()` синхронно (см. текущий докстринг файла). `core/pipeline/runner.py` вызывает его через `await run()`.

## Goals / Non-Goals

**Goals:**
- `fetch_data.py`/сохранение результатов используют асинхронный доступ к БД (`AsyncSessionLocal`), без собственного sync-engine.
- Не сломать существующий вызов `await run_bp3()` из `core/pipeline/runner.py` и синхронный контракт `BaseModule`/`Pipeline`.

**Non-Goals:**
- Не переводим LLM/Tavily-вызовы на async (см. proposal.md).
- Не меняем публичный контракт `BaseModule.process()` — модули остаются `def process(self, ctx)`, не `async def`.

## Decisions

**Ключевая техническая проблема: вложенный event loop.** `run_bp3()` — это `async def`, и вызывается через `await run_bp3()` из `core/pipeline/runner.py`. Значит, когда исполнение доходит до `pipeline.run()` внутри него, мы уже находимся ВНУТРИ работающего event loop (даже если сам `run_bp3()` пока ничего не `await`-ил). Если внутри синхронного `InputDataModule.process()` просто вызвать `asyncio.run(fetch_data())`, Python бросит `RuntimeError: asyncio.run() cannot be called from a running event loop` — потому что loop уже активен на этом же потоке.

**Решение — выполнять `Pipeline.run()` в отдельном потоке, с ОДНИМ event loop на весь прогон.** `run_bp3()` оборачивает вызов в `await asyncio.to_thread(_run_pipeline_in_thread, pipeline)`. `_run_pipeline_in_thread` явно создаёт `asyncio.new_event_loop()`, привязывает его к потоку (`asyncio.set_event_loop`), гоняет `pipeline.run()` синхронно и закрывает loop в конце. Модули (`InputDataModule`/`SaveResultsModule`) берут этот loop через `asyncio.get_event_loop()` и гоняют свои корутины через `loop.run_until_complete(...)`.

Первая версия этого решения (несколько отдельных `asyncio.run(...)` — по одному на каждый async-вызов внутри модулей, без общего loop) была отклонена ПОСЛЕ того, как проявилась на практике при ручной проверке (см. ниже, «Что не сработало с первого раза») — не гипотетический риск, а реальный краш.

```
core/pipeline/runner.py
  await run_bp3()                              ← внешний event loop (уже работает)
      │
      ▼
  await asyncio.to_thread(_run_pipeline_in_thread, pipeline)
      │            создаёт ОДИН loop на весь поток, держит его до конца
      ▼ (внутри потока, синхронно, один и тот же loop)
  InputDataModule.process(ctx) → loop.run_until_complete(fetch_data())
  SaveResultsModule.process(ctx) → loop.run_until_complete(_save(...))
```

**Альтернативы, которые рассмотрели и отклонили:**
- Голый `asyncio.run(...)` внутри `process()` без оборачивания `pipeline.run()` в поток — падает с `RuntimeError`, см. выше.
- Перевести `BaseModule.process()` в `async def` и `Pipeline.run()` в `async def`, чтобы честно `await` доступ к БД без вложенных loop — отклонено: это уже не «только слой БД», а смена контракта всех 9-10 модулей, ровно то, от чего пользователь сознательно отказался в пользу меньшего объёма.
- SQLAlchemy sync engine + `run_sync()`-обёртки в обратную сторону (запускать по-прежнему sync, но подключаться к той же БД, что и async слой, через отдельный sync engine) — это ровно текущее состояние (два разных способа подключения к одной БД), не решает задачу «привести к общей концепции».

## Что не сработало с первого раза (обнаружено при ручной проверке)

**Попытка 1 — отдельный `asyncio.run(...)` на каждый async-вызов внутри модуля.** На Windows это ломает пул соединений `core.database.engine`: каждый `asyncio.run()` создаёт и закрывает СВОЙ event loop, а asyncpg-соединения в пуле остаются привязаны к тому loop'у, под которым были открыты. Второй `asyncio.run()` в том же потоке — уже другой loop, попытка взять соединение из пула, привязанного к первому (уже закрытому) loop'у → `AttributeError: 'NoneType' object has no attribute 'send'` (Proactor/IOCP на Windows). **Исправлено** переходом на один loop на весь прогон (см. Decisions выше).

**Попытка 2 — один loop на поток, но общий `core.database.AsyncSessionLocal`.** Даже с одним loop'ом на поток — при запуске через `core/pipeline/runner.py` (`await run_stage(...)`) preflight-проверка (`_preflight`, тот же файл) уже сходила в БД через `core.database.engine` НА ВНЕШНЕМ loop'е (loop админки/CLI) ДО того, как BP-3 создал свой поток. Общий `engine` — модульный синглтон: его пул соединений привязался к внешнему loop'у первым. Когда поток BP-3 со своим (другим) loop'ом пытается взять соединение из этого же пула — не падает, а **виснет намертво**: другой loop жив, но не крутится в текущем потоке, ответа никогда не будет. Воспроизведено дважды через `core/pipeline/cli.py`, устойчиво.

**Исправлено** отдельным async engine для BP-3 (`src/bp3/db.py`, воскрешён из change `fix-bp3-pipeline-and-entrypoint` — был sync, стал async) с `poolclass=NullPool`: без пула вообще, каждый чекаут — новое соединение, закрывается сразу после использования, привязки к конкретному loop'у не остаётся. Тот же приём уже применяется в `tests/conftest.py` («Предотвращает конфликты транзакций asyncpg между тестами») — не изобретение, а перенос существующего паттерна проекта на новый случай. Проверено дважды подряд через CLI (два независимых потока/loop) — работает без ошибок.

**Побочная находка:** `Source.is_active == 'True'` (сравнение boolean-колонки со строкой вместо `True`/`.is_(True)`) — предсуществующий баг в `fetch_data.py`, молча терпимый sync `psycopg2` (неявный каст), но не `asyncpg` (`UndefinedFunctionError: operator does not exist: boolean = character varying`). Исправлено попутно — без этого проверка 5.1 не прошла бы вообще.

## Risks / Trade-offs

- [Риск] `NullPool` — каждый запрос открывает новое соединение к Postgres (нет переиспользования) → Митигация: приемлемо для объёма BP-3 (один прогон — несколько запросов на пачку новостей, не потоковая нагрузка); тот же trade-off уже принят в тестах проекта.
- [Риск] `asyncio.to_thread` требует Python 3.9+ — сверить минимальную версию проекта (venv сейчас на 3.12, ограничения нет).
- [Риск] Если позже кто-то захочет вызвать `fetch_data()`/сохранение результатов НЕ из `Pipeline.run()` (например, напрямую в тесте) — придётся самому создавать/закрывать event loop или оборачивать в `asyncio.run(...)`, в зависимости от контекста вызывающего кода; это ожидаемая асимметрия при частичном переводе на async.
