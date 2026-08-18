## Why

`ABOUT_PROJECT/DIAGRAMM_IO.md` — DBML-схема БД, которую вручную копируют в dbdiagram.io (сайт не связан с репозиторием, файл специально помечен «изменения нужно переносить вручную при каждом обновлении схемы»). После двух последних изменений (`auto-generate-action-items-from-llm`, `expected-result-add-in-categorized-event`) в `categorized_event` появились новые колонки `task` и `expected_result`, которых в файле сейчас нет — документация разошлась с реальной схемой.

## What Changes

- В блоке `Table categorized_event` (`ABOUT_PROJECT/DIAGRAMM_IO.md`) добавляются две строки-колонки:
  - `task varchar[]` — список задач от LLM (по образцу `event_type.keywords`/`region.name_aliases` в этом же файле).
  - `expected_result varchar` — ожидаемый результат, пока не заполняется никаким модулем (NULL до появления LLM-генератора).
- Правка чисто документационная: код и схема БД уже содержат эти поля (см. миграции `bd1b0f1714a5`, `f09a7c801061`), меняется только описание.

## Capabilities

Изменение не затрагивает поведение системы (документация, не код) — спеки не создаются (`skip_specs: true` в `.openspec.yaml`).

## Impact

- **Файл:** `ABOUT_PROJECT/DIAGRAMM_IO.md` — блок `categorized_event`.
- Код, БД, API не затрагиваются.
