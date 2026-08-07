## Why

`GenerationTaskModule` (`src/bp3/modules/generation_task_module.py`) уже вызывает LLM и кладёт в `ctx.tasks` список из 1–3 конкретных задач на каждую новость — но `SaveResultsModule` эти данные никуда не сохраняет: `CategorizedEvent` не имеет колонки под них, и они теряются при сохранении события. Нужно завести поле под уже готовый выход LLM и одной строкой прокинуть его в сохранение.

## What Changes

- В `CategorizedEvent` (`src/bp3/models.py`) добавляется новое поле `task` — список конкретных задач от LLM (Postgres `ARRAY(String)`, nullable), по образцу `region.name_aliases`/`event_type.keywords` (те же `ARRAY(String)` + `Mapped[list[str] | None]`).
- В `SaveResultsModule.process()` (`src/bp3/modules/save_results_module.py`) добавляется чтение `ctx.tasks` (формат `[{'id': ..., 'tasks': [...]}, ...]`, уже производится `GenerationTaskModule`) и передача списка в конструктор `CategorizedEvent(..., task=...)` — аналогично тому, как туда сейчас прокидываются `action`/`comment`.
- Alembic-миграция на добавление колонки `task` в `categorized_event`.

## Non-goals (сознательно вне этого изменения)

- Никакой новой Celery-задачи и переноса `task` в `action_item` (BP-6) — это отдельное будущее изменение; Celery-обвязка для всех этапов конвейера настраивается отдельно и одновременно для всего проекта, не точечно здесь.
- `expected_result` в `categorized_event` не добавляется: под него в BP-3 пока нет LLM-модуля (в отличие от `tasks`, где `GenerationTaskModule` уже есть) — добавление колонки без источника данных создаст мёртвое поле.
- Изменений в `action_item`/`showcase_event` в этом изменении нет.

## Capabilities

### New Capabilities
- `bp3/categorized-event-tasks`: `categorized_event` хранит список задач, сформированных LLM в BP-3, и пайплайн сохраняет его вместе с остальной разметкой события.

### Modified Capabilities
(нет)

## Impact

- **Модель:** `src/bp3/models.py` (`CategorizedEvent`) — новая колонка `task`.
- **Пайплайн:** `src/bp3/modules/save_results_module.py` — чтение `ctx.tasks` и запись в `CategorizedEvent.task`.
- **Миграция:** новая Alembic-ревизия в `alembic/versions/`.
- **Админка (FastAdmin):** `categorized_event` получает новое поле `task` в списке/форме (автоматически подхватится генерацией CRUD из модели, если ARRAY(String) поддерживается текущей версией FastAdmin — проверить при реализации).
