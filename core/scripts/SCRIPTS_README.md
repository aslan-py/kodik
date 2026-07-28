# Скрипты управления данными

Запускать из корня проекта.

## Общие

| Команда | Что делает |
|---------|-----------|
| `python -m core.scripts.seed_all` | Залить справочники и прогнать все этапы BP-1…BP-6 подряд |
| `python -m core.scripts.clear_data` | Удалить данные пайплайна. Справочники остаются |
| `python -m core.scripts.clear_data --with-dictionaries` | Удалить всё, включая справочники |

## Поэтапные

| Команда | Заполняет |
|---------|-----------|
| `python -m core.scripts.stages.dictionaries` | Все справочники + регионы из `cities.json` |
| `python -m core.scripts.stages.bp1` | `search_task`, `raw_item` |
| `python -m core.scripts.stages.bp2` | `normalized_item` |
| `python -m core.scripts.stages.bp3` | `categorized_event` |
| `python -m core.scripts.stages.bp4` | `showcase_event` (собирает конвейером, не подделывает) |
| `python -m core.scripts.stages.bp5` | `alert` |
| `python -m core.scripts.stages.bp6` | `action_item` |

Каждый скрипт чистит свой слой и всё, что ниже по потоку, затем заливает заново.
Предыдущие слои он не заполняет — их нужно залить самому, в порядке таблицы.

Очистка `stages.dictionaries` сносит и данные пайплайна: иначе FK не дадут
удалить конкурента, на которого ссылается задача сбора.
