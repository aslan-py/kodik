## 1. `run_bp3()` — выполнение пайплайна в отдельном потоке

- [x] 1.1 В `src/bp3/pipeline.py::run_bp3()` заменить `result = pipeline.run()` на `result = await asyncio.to_thread(pipeline.run)`

## 2. `fetch_data.py` на async

- [x] 2.1 `fetch_data()`, `fetch_news_stats()`, `fetch_seed_urls()` — сделать `async def`, `Session()`/`session.execute(...)` заменить на `async with AsyncSessionLocal() as session: await session.execute(...)`
- [x] 2.2 Убрать локальный `DATABASE_URL`/`engine`/`Session` (или импорт из `src/bp3/db.py`, если change `fix-bp3-pipeline-and-entrypoint` уже применён) — заменить на `from core.database import AsyncSessionLocal`

## 3. Вызывающая сторона (`InputDataModule`) — мост через `asyncio.run`

- [x] 3.1 В `src/bp3/modules/input_data_module.py::process()` (остаётся синхронным) — вызовы `fetch_data()`/`fetch_news_stats()`/`fetch_seed_urls()` обернуть в `asyncio.run(...)`, т.к. они теперь `async def`
- [x] 3.2 Убедиться, что `process()` вызывается ИЗ потока `asyncio.to_thread(...)` — подтверждено эмпирически прогонами 5.1/5.2 (иначе была бы `RuntimeError`/зависание, чего не случилось)

## 4. `save_results_module.py` на async

- [x] 4.1 Метод сохранения (весь блок `with Session() as session: ...`) — сделать `async def`, переключить на `AsyncSessionLocal`/`await session.execute(...)`/`await session.commit()`
- [x] 4.2 В `SaveResultsModule.process()` (остаётся синхронным) — обернуть вызов асинхронного метода сохранения в `asyncio.run(...)`
- [x] 4.3 Убрать `src/bp3/db.py` (если существует после `fix-bp3-pipeline-and-entrypoint`) — он был нужен только для sync-подключения, после этого change все обращения идут через `AsyncSessionLocal`

## 5. Проверка вручную

- [x] 5.1 Прогнать `python -m src.bp3.pipeline` — убедиться, что нет `RuntimeError` про event loop, данные сохраняются как раньше. По пути потребовались две незапланированные правки (см. design.md): (а) один `event loop` на весь прогон вместо `asyncio.run()` на каждый вызов — иначе рвётся пул соединений на Windows; (б) `Source.is_active == 'True'` → `.is_(True)` — предсуществующий баг, который молча терпел sync `psycopg2`, но не терпит `asyncpg`
- [x] 5.2 Прогнать этап 3 через `core/pipeline/cli.py`/админку — обнаружен и исправлен реальный дедлок (не просто риск): общий `core.database.engine` привязывает пул соединений к первому тронувшему его event loop (тут — preflight-проверка на внешнем loop админки/CLI), поток BP-3 со своим loop подвисал намертво пытаясь получить оттуда соединение. Исправлено отдельным engine с `NullPool` для BP-3 (`src/bp3/db.py`, воскрешён — теперь async, не sync) — тот же приём, что уже в `tests/conftest.py`. Проверено дважды подряд (два независимых потока/loop) — работает
- [~] 5.3 Прогнать `run_all()` — **пропущено сознательно**: `run_all()` включает этап 1 (BP-1), пользователь попросил не тратить время на его прогон/проверку ни в каком виде. Цепочка BP-2→BP-3→BP-4 проверена частично: BP-3 прогнан отдельно дважды (5.2), BP-4 отдельно в рамках change `add-bp6-action-item-generation`
