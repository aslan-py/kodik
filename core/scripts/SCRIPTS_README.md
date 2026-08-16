# Скрипты управления данными

Все команды выполняются из корня проекта внутри активированного виртуального
окружения. Перед работой настройте `.env` по `.env.example`.

## Развернуть с нуля

Для пустого локального окружения:

```bash
pip install -r requirements.txt -r requirements-dev.txt
docker compose up -d
python -m alembic upgrade head
python -m core.scripts.seed_all
uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
```

`seed_all` заполняет справочники и детерминированные демо-данные BP1–BP6.
После запуска API доступны Swagger (`/docs`) и админка (`/admin`). Порт берите
из `API_PORT` в `.env`, если он отличается от 8001.

Есть интерактивная альтернатива «одной командой»:

```bash
python -m core.scripts.universal_script_1
```

Она устанавливает зависимости, применяет миграции, заполняет BP1–BP5 и
поднимает API. Для предсказуемого и дешёвого прогона скрипт намеренно берёт
демо-сидеры BP1 и BP3, хотя реальные реализации обоих этапов существуют.
Перед BP5 он отдельно спрашивает, разрешена ли настоящая отправка алертов.

## Тестовый набор для реального сбора

`core/data/*.csv` — отдельная конфигурация для проверки живого BP1:

- 4 конкурента, включая ИНН;
- 9 правдоподобных источников;
- 5 поисковых триггеров;
- 56 заранее заданных задач сбора.

Загрузить набор:

```bash
python -m core.scripts.seed_data --dry-run
python -m core.scripts.seed_data
python -m core.pipeline.cli 1 real
```

Первый вызов только показывает объём. Второй идемпотентно читает
`competitor.csv`, `source.csv`, `trigger.csv` и `search_task.csv`. Третий
запускает настоящий сбор: сеть, Redis, классификацию сайтов и при
необходимости LLM. Перед обходом BP1 автоматически досоздаёт недостающие
задачи без триггера для активных пар «конкурент × источник».

Если нужно только сформировать покрытие и увидеть его объём без сети:

```bash
python -m src.bp1.search_task_coverage
```

Набор `core/data/` не является демо-витриной. В нём конфигурация для живых
сайтов, но нет готовых новостей. Демо-данные `core/scripts/scripts_data/`,
напротив, содержат фиксированные новости и используются `stages.bp1` и
`seed_all` без обращения к внешним источникам.

## Прогнать конвейер на минимальных тестовых данных

Дешёвая проверка без сети и LLM:

```bash
python -m core.scripts.clear_data --with-dictionaries
python -m core.scripts.stages.simple_dictionaries
python -m core.scripts.stages.bp1_stub
python -m core.pipeline.cli 2
```

`simple_dictionaries` создаёт узкие справочники под шесть синтетических
новостей `bp1_stub`. Настоящий конвейер BP2 отбрасывает четыре новости
правилами фильтрации, так что после него ожидаются две строки
`normalized_item` со `status=ok`. Этот сценарий проверяет вход BP1, связи с
BP2 и бизнес-фильтры за секунды, но не проверяет реальные сайты и не запускает
дорогие BP3/LLM. Команда `core.scripts.stages.bp2` здесь не подходит: это
самостоятельный демо-сидер следующего слоя, а не обработка `bp1_stub`.

## Наполнить витрину демо-данными

Полный фиксированный набор (~49 конкурентов и 100+ новостей):

```bash
python -m core.scripts.stages.dictionaries
python -m core.scripts.stages.bp1
python -m core.scripts.stages.bp2
python -m core.scripts.stages.bp3
python -m core.scripts.stages.bp4
python -m core.scripts.stages.bp5
python -m core.scripts.stages.bp6
```

Эквивалентная короткая команда:

```bash
python -m core.scripts.seed_all
```

Новости лежат в `core/scripts/scripts_data/news_dataset.csv`, города — в
`cities.json`, а порядок снимков задаёт `stages/bp1.py`. Это сценарий для
витрины, API и BI: он не делает сетевых запросов и воспроизводится одинаково.

## Три способа наполнить BP1

| Способ | Что даёт | Стоимость | Когда использовать |
|---|---|---|---|
| `python -m core.pipeline.cli 1 real` | Живые данные из активных источников; задачи покрытия создаются автоматически | Сеть, Redis, время и лимиты LLM | Реальная проверка сбора |
| `python -m core.scripts.stages.bp1` | Большой фиксированный демо-набор из `scripts_data/` | Без сети, но много строк | Наполнить витрину и BI |
| `python -m core.scripts.stages.bp1_stub` | 6 синтетических новостей | Минимальная | Быстро проверить весь конвейер |

В админке запуск этапа BP1 работает так же: режим «реальный сбор» сначала
синхронизирует задачи, затем обходит источники; режим заглушки использует
`bp1_stub`. В CLI режим можно выбрать явно: `1 real` или `1 stub`.

## Очистка

```bash
python -m core.scripts.clear_data
python -m core.scripts.clear_data --with-dictionaries
```

Без флага удаляются все данные пайплайна от `search_task` до `action_item`,
но справочники сохраняются. С флагом после данных удаляются и справочники —
база остаётся со схемой, но без прикладных строк.

Самостоятельный скрипт конкретного этапа действует уже: он очищает свой слой
и всё, что построено ниже по потоку, затем заново заполняет только этот слой.
Например, `stages.bp3` удалит BP3–BP6, сохранит BP1–BP2 и заново создаст BP3.
Очистка и вставка идут в одной транзакции.

## Справочник команд

| Команда | Что делает |
|---|---|
| `python -m core.scripts.seed_all` | Справочники и демо-данные BP1–BP6 |
| `python -m core.scripts.seed_data` | Конфигурация живого BP1 из `core/data/*.csv` |
| `python -m core.scripts.clear_data` | Все данные пайплайна, справочники остаются |
| `python -m core.scripts.clear_data --with-dictionaries` | Все данные и справочники |
| `python -m core.scripts.universal_script_1` | Интерактивное развёртывание демо BP1–BP5 и запуск API |
| `python -m core.scripts.stages.dictionaries` | Полные демо-справочники и регионы |
| `python -m core.scripts.stages.simple_dictionaries` | Минимальные справочники для `bp1_stub` |
| `python -m core.scripts.stages.bp1` | Демо `search_task` и `raw_item` |
| `python -m core.scripts.stages.bp1_stub` | Минимальные `search_task` и 6 `raw_item` |
| `python -m core.scripts.stages.bp2` | `normalized_item` |
| `python -m core.scripts.stages.bp3` | Детерминированный демо-слой `categorized_event` |
| `python -m core.scripts.stages.bp4` | `showcase_event` через реальный BP4 |
| `python -m core.scripts.stages.bp5` | `alert` через реальный BP5 без внешней отправки |
| `python -m core.scripts.stages.bp6` | `action_item` |
| `python -m core.scripts.stages.bp7` | Демо-очередь `source_candidate` |

Каждый новый исполняемый модуль в `core/scripts/` должен быть добавлен в этот
справочник и в подходящий сценарный раздел. Если у команды нет актуального
назначения, ей не место среди исполняемых скриптов.
