## Why

`categorized_event.task` (список задач от LLM, BP-3) и `categorized_event.expected_result` теперь реально формируются (см. change `fix-bp3-pipeline-and-entrypoint`), но никуда дальше не переносятся. Таблица `action_item` (BP-6 — план действий, читает DataLens/веб-форма) остаётся пустой, если не завести туда данные руками через API/админку. Ваш же архивный change `auto-generate-action-items-from-llm` изначально и сознательно отнёс этот перенос к «отдельному будущему изменению» — пришло время его сделать. Заглушка этапа 6 в реестре пайплайна (`core/pipeline/registry.py`) до сих пор генерирует случайные демо-строки вместо реального переноса.

## What Changes

- Реализуется `run_bp6()` в новом `src/bp6/pipeline.py` — по контракту `run_bp2`/`run_bp4`/`run_bp5` (`async def -> dict`), чтобы встать в `core/pipeline/registry.py` вместо текущей заглушки.
- Отбираются `showcase_event` с приоритетом **П1 или П2** (по докстрингу `ActionItem`: «по событию П1/П2 человек заводит задачу» — П3/П4 не значимы для автозадач), у которых есть непустой `categorized_event.task` (через `categorized_event_id`).
- На каждую строку `categorized_event.task[]` заводится **отдельная строка `action_item`** (не одна строка со списком) — `task` = один элемент массива, `department_id` резолвится из `categorized_event.department_id` (тот же отдел, что уже определён LLM/`ActionPlanningModule` на BP-3), `deadline`/`expected_result` копируются с `categorized_event`, `status=open` (дефолт модели), `assigned_user_id` остаётся `NULL` — задача заводится на отдел, конкретного исполнителя выбирает человек.
- Добавляется watermark-поле на `showcase_event` (например, `action_items_generated_at`) для идемпотентности: событие обрабатывается **один раз**; если `categorized_event.task` позже поменяется (перекатегоризация), уже сгенерированные `action_item` НЕ перезаписываются и не дублируются — это сознательное решение первой версии (дальнейшая правка задач — работа отдела, не автоматики).
- `core/pipeline/registry.py` — этап 6 (`STAGES[6]`) переключается с заглушки (`core/scripts/stages/bp6.py`) на `run_bp6()`, `is_stub=False`.
- `core/scripts/stages/bp6.py` (текущая заглушка со случайными демоданными) — не удаляется автоматически в рамках этого change, но перестаёт быть тем, что вызывает реестр; окончательная судьба файла (удалить/оставить для тестов) решается при реализации.

## Capabilities

### New Capabilities
- `bp6/action-item-generation`: автоматический перенос задач, сформированных LLM на BP-3 (`categorized_event.task`), в план действий (`action_item`) — по одной строке на задачу, только для приоритетных (П1/П2) событий, один раз на событие.

## Impact

- Код: `src/bp6/pipeline.py` (новый), `src/bp6/crud.py` (новый, по образцу `src/bp5/crud.py`), `core/pipeline/registry.py`.
- Модель: `showcase_event` — новая колонка-watermark (`action_items_generated_at` или аналог).
- Миграция: новая Alembic-ревизия на добавление колонки.
- Не входит: UI/веб-форма для ручного редактирования `action_item` — уже существует (`api/crud/action_items.py`), не трогаем.
