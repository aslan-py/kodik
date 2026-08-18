## 1. Обновление DBML

- [x] 1.1 В `ABOUT_PROJECT/DIAGRAMM_IO.md`, блок `Table categorized_event`, добавить строку `task varchar[] [null, note: "Список задач от LLM (GenerationTaskModule), 1-3 практических шага. Массив — по образцу event_type.keywords/region.name_aliases"]` после строки `comment`. Уточнение по ходу: фактически размещена после `action` (перед `deadline`), чтобы совпадать с реальным порядком колонок в модели — см. задачу 2.1.
- [x] 1.2 В том же блоке добавить строку `expected_result varchar [null, note: "Ожидаемый результат по событию. Источника в BP-3 пока нет — NULL, задел под будущий LLM-модуль"]` после `task`. Фактически размещена после `comment` (перед `llm_model`) — по факту порядка в модели.

## 2. Проверка

- [x] 2.1 Свериться, что порядок и формат новых строк соответствуют остальным колонкам таблицы (тип, `[null, note: "..."]`), и что список колонок `categorized_event` в файле теперь совпадает с `src/bp3/models.py`. Проверено: `CategorizedEvent.__table__.columns.keys()` даёт `action, task, deadline, department_id, comment, expected_result, llm_model, ...` — порядок в DBML скорректирован под это (изначальное размещение обеих колонок подряд после `comment` не совпадало с моделью, исправлено).
