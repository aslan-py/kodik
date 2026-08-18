## 1. Модель

- [x] 1.1 В `src/bp3/models.py` добавить в `CategorizedEvent` поле `task: Mapped[list[str] | None] = mapped_column(ARRAY(String), comment=...)` — импорт `ARRAY` из `sqlalchemy.dialects.postgresql` (как в `src/bp2/models.py`/`src/bp5/models.py`), комментарий в духе «Список конкретных задач от LLM (GenerationTaskModule)».

## 2. Миграция

- [x] 2.1 Сгенерировать Alembic-ревизию (`alembic revision --autogenerate -m "add categorized_event.task"`) поверх текущей головной ревизии.
- [x] 2.2 Проверить сгенерированный `upgrade`/`downgrade` — только `add_column`/`drop_column` на `categorized_event.task`, без лишних диффов от несвязанных моделей.
- [x] 2.3 Прогнать миграцию на локальной БД (`alembic upgrade head`), убедиться что откат (`alembic downgrade -1`) тоже проходит.

## 3. Пайплайн BP-3

- [x] 3.1 В `src/bp3/modules/save_results_module.py`, в `SaveResultsModule.process()`, добавить сбор `ctx.tasks` в `data_by_id` по аналогии с `ctx.actions`/`ctx.comments` (`data_by_id.setdefault(item['id'], {})['task'] = item.get('tasks')`).
- [x] 3.2 Передать `task=fields.get('task')` в конструктор `CategorizedEvent(...)`.

## 4. Смежные слои чтения (по необходимости)

- [x] 4.1 Добавить `task: list[str] | None` в `CategorizedEventRead` (`api/schemas/categorized_event.py`).
- [x] 4.2 Добавить `task` в `list_display` (и при необходимости `list_display_labels`) `CategorizedEventAdmin` (`api/admin/pipeline.py`) — прецедент рендеринга `ARRAY(String)` в списке уже есть (`region.name_aliases`, `event_type.keywords`).

## 5. Проверка

- [x] 5.1 Прогнать BP-3 end-to-end на демо-данных, убедиться что `categorized_event.task` заполняется значениями из `GenerationTaskModule` и пуст/NULL, когда `ctx.tasks` не содержит записи для события. Прогнано через `main.py` на normalized_item_id 229/230 — оба сохранились с непустым `task`, ровно как вернул `GenerationTaskModule`.
- [x] 5.2 Сознательно пропущено: тестов BP-3 в проекте нет, а `SaveResultsModule` создаёт свою sync-сессию прямо на настройки `.env` (без dependency injection) — pytest-тест по конвенции проекта (`tests/conftest.py`, async-сессия с откатом) писать не на чем без правки чужого модуля. Задача 5.1 (живой прогон) уже дала конкретное подтверждение на реальных данных.
