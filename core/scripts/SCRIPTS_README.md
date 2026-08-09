# Скрипты управления данными

Запускать из корня проекта.

## Общие

| Команда | Что делает |
|---------|-----------|
| `python -m core.scripts.seed_all` | Залить справочники и прогнать все этапы BP-1…BP-6 подряд |
| `python -m core.scripts.clear_data` | Удалить данные пайплайна. Справочники остаются |
| `python -m core.scripts.clear_data --with-dictionaries` | Удалить всё, включая справочники |
| `python -m core.scripts.universal_script_1` | Установить зависимости, накатить миграции, прогнать BP-1…BP-5 (BP-1/BP-3 — заглушки, BP-2/BP-4/BP-5 — настоящие конвейеры) и поднять `uvicorn` с `/docs`. Одна команда для «посмотреть, как всё работает целиком» — см. докстринг файла(Что бы скрипт отработал обязательно нужно получить и поставить TELEGRAM_BOT_TOKEN в файл .env) |

## Поэтапные

| Команда | Заполняет |
|---------|-----------|
| `python -m core.scripts.stages.dictionaries` | Все справочники + регионы из `scripts_data/cities.json` |
| `python -m core.scripts.stages.simple_dictionaries` | Узкий набор справочников (1 конкурент, 1 источник, фильтры, маршрутизация) под 6-новостной тестовый сценарий `bp1_stub` |
| `python -m core.scripts.stages.bp1` | `search_task`, `raw_item` (полный демо-датасет) |
| `python -m core.scripts.stages.bp1_stub` | `search_task`, `raw_item` — минимальная заглушка из 6 синтетических новостей для дешёвой сквозной проверки (требует `simple_dictionaries`) |
| `python -m core.scripts.stages.bp2` | `normalized_item` |
| `python -m core.scripts.stages.bp3` | `categorized_event` |
| `python -m core.scripts.stages.bp4` | `showcase_event` (собирает конвейером, не подделывает) |
| `python -m core.scripts.stages.bp5` | `alert` (собирает конвейером, не подделывает) |
| `python -m core.scripts.stages.bp6` | `action_item` |
| `python -m core.scripts.stages.bp7` | `source_candidate` (демо-заглушка очереди кандидатов) |

Каждый скрипт чистит свой слой и всё, что ниже по потоку, затем заливает заново.
Предыдущие слои он не заполняет — их нужно залить самому, в порядке таблицы.

Очистка `stages.dictionaries` сносит и данные пайплайна: иначе FK не дадут
удалить конкурента, на которого ссылается задача сбора.

## Откуда берутся демо-данные

Всё содержимое демо лежит в `scripts_data/` (см. README там же):

- `news_dataset.csv` — новости конкурентов. Одна строка = одна новость, из
  неё собираются сырьё (BP-1), факты (BP-2) и разметка (BP-3), а также
  справочник конкурентов. Загрузчик — `stages/news_data.py`;
- `cities.json` — справочник регионов.

Сценарий выгрузок (какой снимок, когда снят, какие новости содержит) описан
в `SNAPSHOTS` — `stages/bp1.py`. Добавить новость = дописать строку в CSV и
упомянуть её id в снимке.
