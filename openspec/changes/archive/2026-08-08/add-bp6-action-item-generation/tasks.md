## 1. Миграция

- [x] 1.1 Добавить в `ShowcaseEvent` (`src/bp4/models.py`) поле `action_items_generated_at: Mapped[datetime | None]` — watermark, по аналогии с `alerted_at`
- [x] 1.2 Alembic-ревизия на новую колонку (заодно почистил сломанную цепочку миграций — `afbc57e951f4` ссылался на ревизию, удалённую при мерже ветки коллеги)

## 2. CRUD-слой BP-6

- [x] 2.1 Создать `src/bp6/crud.py` — по образцу `src/bp5/crud.py`: выборка `showcase_event` с `priority IN ('П1', 'П2') AND action_items_generated_at IS NULL`, джойн/подгрузка связанного `categorized_event` (`task`, `expected_result`, `department_id`) через `categorized_event_id`
- [x] 2.2 Метод вставки пачки `action_item` (по одной строке на элемент `task[]`)
- [x] 2.3 Метод простановки watermark (`action_items_generated_at`) на обработанные `showcase_event`, независимо от того, создались ли строки `action_item`

## 3. Пайплайн

- [x] 3.1 Создать `src/bp6/pipeline.py::run_bp6() -> dict` — контракт как у `run_bp2`/`run_bp4`/`run_bp5`: своя сессия, commit, сводка прогона
- [x] 3.2 Логика: отобрать события → для каждого прочитать `task[]` связанного `categorized_event` → на каждый элемент собрать строку `action_item` (`task`=элемент, `department_id`=`categorized_event.department_id`, `deadline`=`categorized_event.deadline`, `expected_result`=`categorized_event.expected_result`, `assigned_user_id=None`, `status` по умолчанию модели) → вставить пачкой → проставить watermark на ВСЕ обработанные события (в т.ч. с пустым `task[]`). Доп. защита: событие с `categorized_event.department_id IS NULL` пропускается целиком (`ActionItem.department_id` NOT NULL)
- [x] 3.3 Сводка прогона: сколько событий рассмотрено, сколько из них дали хотя бы одну задачу, сколько строк `action_item` создано всего

## 4. Реестр пайплайна

- [x] 4.1 В `core/pipeline/registry.py` — `STAGES[6]` переключить `run` на `run_bp6`, `is_stub=False`
- [x] 4.2 Решение: `core/scripts/stages/bp6.py` оставлен как есть, не удалён — по тому же прецеденту, что `bp1.py`/`bp1_stub.py` (полный демо-сидер сосуществует с реальным этапом пайплайна, реестр его больше не вызывает, но команда `python -m core.scripts.stages.bp6` остаётся рабочей для сидинга демоданных отдельно)

## 5. Проверка вручную

- [x] 5.1 На данных с уже заполненным `categorized_event.task` (из change `fix-bp3-pipeline-and-entrypoint`) прогнать BP-4, затем этап 6 через `core/pipeline/cli.py`/админку — сверить, что `action_item` заполнился по П1/П2-событиям, по одной строке на задачу
- [x] 5.2 Прогнать этап 6 повторно — убедиться, что дублей не появилось и watermark не даёт повторно обработать те же события
- [x] 5.3 Проверить событие с приоритетом П3/П4 — подтверждено п.5.1 (события 501/502, П4, `action_items_generated_at` осталось `NULL`, `action_item` не создан), у которого есть `task[]` — убедиться, что для него `action_item` НЕ создаётся
