## Why

BP-3 — единственная часть проекта, где доступ к БД остаётся синхронным (`create_engine`/`sessionmaker`, sync `psycopg2`), пока весь остальной проект (BP-1/2/4/5/7, API) работает через `core.database.AsyncSessionLocal`. Это сознательно оставили как есть при первой интеграции BP-3 (см. [[bp3-bp6-coordination]] — не делать async-рефакторинг без явного запроса, был потенциальный конфликт с параллельной разработкой коллеги). Ветка коллеги (`llm_function`) уже влита, конфликт снят — пользователь явно просит перевести BP-3 на async, чтобы не противоречить общей концепции проекта.

## What Changes

- `src/bp3/fetch_data.py` (`fetch_data`, `fetch_news_stats`, `fetch_seed_urls`) и `src/bp3/modules/save_results_module.py` переводятся на асинхронный доступ к БД. `src/bp3/db.py` (sync `engine`/`Session`, заведённый в предыдущем change) не удаляется, а переписывается на async — **не** `core.database.AsyncSessionLocal` напрямую: выяснилось при реализации, что общий движок с пулом соединений привязывается к первому event loop'у, который его коснулся, а BP-3 гоняет `Pipeline.run()` в отдельном потоке со своим loop на каждый прогон — общий пул либо падает, либо виснет при повторном использовании из другого loop'а. Решение — свой `engine` с `NullPool` (без переиспользуемого пула), см. design.md, Decisions.
- Только слой доступа к БД. Вызовы LLM (`self.structured_llm.invoke(...)`) и Tavily (`client.search(...)`) остаются синхронными — они и так блокирующие внешние HTTP-вызовы, их перевод на async — отдельный, более крупный объём работы (контракт `BaseModule.process()`/`Pipeline.run()` в `models_llm.py` тоже пришлось бы менять), вне рамок этого change.
- Сам контракт `BaseModule.process(self, ctx) -> ctx` (синхронный) и `Pipeline.run()` (синхронный) НЕ меняются — модули как вызывались синхронно одной цепочкой, так и вызываются. Мост между синхронным вызовом модуля и новым асинхронным доступом к БД — см. design.md, там есть техническая тонкость (вложенный event loop).
- `run_bp3()` в `src/bp3/pipeline.py` меняет способ выполнения `Pipeline.run()` — см. design.md, Decisions.

## Capabilities

(нет — `skip_specs: true` в `.openspec.yaml`: меняется только внутренняя реализация доступа к БД, наблюдаемое поведение — что попадает в `categorized_event`/`source_candidate` и в каком виде — не меняется)

## Impact

- Код: `src/bp3/fetch_data.py`, `src/bp3/modules/save_results_module.py`, `src/bp3/modules/input_data_module.py`, `src/bp3/pipeline.py`, `src/bp3/db.py` (переписан на async с `NullPool`, не удалён). Заодно исправлен предсуществующий баг `Source.is_active == 'True'` (сравнение boolean-колонки со строкой) — молча работал под sync `psycopg2`, не работает под `asyncpg` (см. design.md).
- Зависимость: этот change применяется ПОСЛЕ `fix-bp3-pipeline-and-entrypoint` (нужен рабочий, синхронизированный код, прежде чем переводить его на async).
- Тесты: если для BP-3 появятся тесты на прямой вызов `fetch_data()`/`save_results_module` — учесть, что сигнатуры станут `async def`.
