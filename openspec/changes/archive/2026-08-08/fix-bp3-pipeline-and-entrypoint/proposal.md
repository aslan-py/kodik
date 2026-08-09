## Why

Влитый из ветки `llm_function` код BP-3 (`categorized_event` + `source_candidate`) не запускается: `src/bp3/modules/save_results_module.py` содержит синтаксическую ошибку (`IndentationError`), которая при импорте роняет весь `core/pipeline/registry.py` — то есть не только «Этап 3», а весь конвейер и вся админка недоступны. После починки отступа всплывают ещё два бага: `SourceCandidate` используется без импорта, `SourceFinderModule` используется в корневом `main.py` без импорта (этот исчезнет сам собой при удалении `main.py`, см. ниже). Отдельно — `src/bp3/pipeline.py::run_bp3()` (реальная точка входа, которую дёргает админка/CLI) не синхронизирована с обновлённым корневым `main.py`: не хватает `ExpectedResultModule` в списке модулей, а `domains_found` считает не то (после смены формата `domains_to_add` с плоского списка на `dict[competitor_id, ...]`). Ключ LLM — `OPENROUTER_API_KEY` (пользователь вручную вернул его во всех местах после эксперимента коллеги с `KODIK_API_KEY`; `config.py`/`main.py`/`.env` уже согласованы между собой, отдельно чинить не нужно). Заодно у новых модулей нет докстрингов, есть дублирование ручной сборки sync-подключения к БД, ключи/модель читаются напрямую через `os.getenv` вместо общего `core.config.settings`, а `fetch_data()` жёстко ограничивает выборку 10 записями за прогон — это стоит снять, раз объём теперь и так контролируется минимальной заглушкой BP-1 (см. change `add-bp1-minimal-pipeline-stub`).

## What Changes

- **Синтаксис:** починить отступ в `save_results_module.py` — блок сохранения `source_candidate` выносится ИЗ цикла по новостям (сейчас случайно оказался внутри него — привёл бы к дублям на каждую новость) и выполняется один раз за прогон.
- **Импорты:** добавить `from src.bp7.models import SourceCandidate` в `save_results_module.py`.
- **Единая точка входа:** `src/bp3/pipeline.py::run_bp3()` синхронизируется с актуальным списком модулей (добавляется `ExpectedResultModule`), метрика `domains_found` считается как суммарное число найденных доменов по всем конкурентам (не число конкурентов). Корневой `main.py` удаляется — вместо него `python -m src.bp3.pipeline` (как у BP-2), `__main__`-блок в `src/bp3/pipeline.py` раскомментировывается/актуализируется.
- **Лимит записей за прогон:** убирается `.limit(10)` в `src/bp3/fetch_data.py::fetch_data()` — раньше это была защита от неконтролируемого расхода токенов на полном демо-датасете BP-1, теперь объём и так под контролем через минимальный стаб BP-1 (отдельный change); фиксированный потолок в 10 больше не нужен и мешает реальному прогону, если накопилось больше необработанных новостей.
- **Настройки через pydantic:** `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `MODEL` переносятся из разрозненных `os.getenv(...)` (`src/bp3/config.py`, `src/bp3/pipeline.py`, `src/bp3/modules/source_finder_module.py`) в `core/config.py::Settings` — по тому же паттерну, что уже принят в проекте (`mail_*`, `telegram_bot_token`, `true_alerting` и т.д.). BP-3 начинает читать `core.config.settings`, как остальные BP.
- **Стиль:** добавляются докстринги классам/методам модулей, тронутых в этом мерже (`action_planning_module.py`, `comment_action_module.py`, `expected_result_module.py`, `generation_task_module.py`, `source_finder_module.py`, `config.py`, `save_results_module.py`). Дублирующаяся ручная сборка `DATABASE_URL`/`engine`/`Session` (сейчас в `fetch_data.py` и `save_results_module.py`) выносится в один общий `src/bp3/db.py` — BP-3 остаётся синхронным (см. [[bp3-bp6-coordination]]), просто без копипаста подключения.
- **Не входит в этот change:** заглушка этапа 6 в реестре не убирается (`action_item` не заполняется — отдельный change), заглушка этапа 1 не трогается (отдельный change), UNIQUE на `source_candidate.domain` не чинится (известная мелочь, не блокер), перевод BP-3 на async — отдельный change.

## Capabilities

### Modified Capabilities
- `bp3/categorized-event-expected-result`: поле `expected_result` теперь реально формируется LLM-модулем (`ExpectedResultModule`) на этапе BP-3 через штатную точку входа `run_bp3()`, а не остаётся пустым в ожидании будущего источника данных.

## Impact

- Код: `src/bp3/modules/save_results_module.py`, `src/bp3/pipeline.py`, `src/bp3/fetch_data.py`, `src/bp3/db.py` (новый), `src/bp3/modules/*.py` (докстринги), `src/bp3/config.py`, `src/bp3/modules/source_finder_module.py`, `core/config.py` (новые поля `Settings`), `main.py` (удаляется).
- Тесты: нет специфичных тестов на этот путь сейчас — при реализации проверить, не появятся ли.
- Прочее: не трогает БД/миграции — колонки уже добавлены предыдущими change.
