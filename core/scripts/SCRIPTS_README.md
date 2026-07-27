# Скрипты управления данными

| Модуль | Команда | Назначение |
|--------|---------|-----------|
| `core.scripts.seed_all` | `python -m core.scripts.seed_all` | Заполнить все справочники и вставить демо-данные (запускать один раз при развёртывании) |
| `core.scripts.seed_raw_test` | `python -m core.scripts.seed_raw_test` | Пересоздать тест-данные для BP-2: чистит `normalized_item → raw_item → search_task`, вставляет 13 `raw_item` с разными сценариями. Перезапускаемый. |
| `core.scripts.clear_data` | `python -m core.scripts.clear_data` | Удалить все данные (справочники сохраняются) |
