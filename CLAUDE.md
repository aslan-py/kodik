# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Дополняет [AGENTS.md](AGENTS.md) (общие команды, соглашения по моделям,
ветки) и [Правила.md](Правила.md) (стиль работы). Здесь — то, что не видно
из одного файла и требует чтения нескольких.

> AGENTS.md местами устарел: там сказано «тестов пока нет» и «bp2–bp7
> закомментированы» — на деле реализованы все семь этапов, тестов ~600+,
> а Celery (там же описанный как будущее) уже подключён и наполнен.

## Окружение

**Виртуальное окружение лежит ВНЕ репозитория** — в родительской папке
(`../.venv-kodik/`), поэтому запускать надо явным путём:

```bash
../.venv-kodik/Scripts/python.exe -m pytest tests/bp1/ -q   # Windows
```

Python 3.12+ (код использует `StrEnum`, `datetime.UTC`, `X | Y` в
аннотациях, PEP 695 generics — на 3.9 не запустится).

## Команды

```bash
# Тесты
../.venv-kodik/Scripts/python.exe -m pytest tests/ -q
../.venv-kodik/Scripts/python.exe -m pytest tests/bp1/adaptive/ -v
../.venv-kodik/Scripts/python.exe -m pytest tests/bp1/adaptive/test_parser.py::test_parse_extracts_items
../.venv-kodik/Scripts/python.exe -m pytest tests/bp1/ -k "quality or adapter"

# Линт и формат (ruff: одинарные кавычки, 80 символов)
../.venv-kodik/Scripts/python.exe -m ruff check src/ tests/
../.venv-kodik/Scripts/python.exe -m ruff check src/ tests/ --fix
../.venv-kodik/Scripts/python.exe -m ruff format src/ tests/

# Конвейер (CLI поверх PipelineRunService)
python -m core.pipeline.cli 1        # один этап (1..7)
python -m core.pipeline.cli 1 real   # этап 1 настоящей реализацией
python -m core.pipeline.cli 1 stub   # этап 1 заглушкой
python -m core.pipeline.cli all      # весь конвейер

# Сбор данных (этап 1) напрямую
python -m src.bp1.cli source lenta.ru
python -m src.bp1.cli competitor "Сбербанк" --inn 7707083893
python -m src.bp1.cli all
python -m src.bp1.cli add-source https://www.lenta.ru/news
```

Инфраструктура (Postgres, Redis, API, воркеры, Beat, Flower, Grafana) —
`docker compose up -d --build`; операции с очередями — в
[CELERY_README.md](CELERY_README.md).

**Тестам нужен живой Postgres** — `tests/conftest.py` создаёт движок из
`settings.database_url`; без него бо́льшая часть сюита не соберётся/упадёт.

## Архитектура: конвейер из 7 этапов

Данные текут слоями, каждый следующий читает предыдущий:

```
BP-1 сбор      RawItem          src/bp1/  ← основной объём кода
BP-2 очистка   NormalizedItem   src/bp2/
BP-3 LLM       CategorizedEvent src/bp3/
BP-4 витрина   ShowcaseEvent    src/bp4/
BP-5 алерты    Alert            src/bp5/
BP-6 BI                         src/bp6/
BP-7 админка                    src/bp7/
```

**`core/pipeline/registry.py` — единственный источник правды** о том, какая
функция стоит за каким этапом. Точка входа этапа живёт в
`src/bpN/pipeline.py` (`run_bp1`…`run_bp6`, у седьмого — `run_bp7_promotion`),
сама открывает сессию и Redis и возвращает сводку прогона; реестр вызывает
её без аргументов. Он же знает про `requires` (модель предыдущего слоя для
preflight), `run_reparse` (пересборка новыми правилами — есть только у
BP-2, поэтому `run_bp2` принимает `reparse`/`raw_item_ids`) и `run_stub`
(заглушка — есть только у BP-1, переключается настройкой `TRUE_PARSING`).

**Оркестрация прогонов — отдельный слой поверх реестра**
(`core/pipeline/service.py`, `PipelineRunService`): создаёт durable
`PipelineRun`/`PipelineStageRun` в БД, гарантирует, что параллельно не
запустится второй прогон того же вида (`PipelineRunConflict`), и через
Celery-цепочку (`celery.chain`) прогоняет этапы по очереди. `PipelineSchedule`
хранит расписание в БД; beat-задача `dispatch_scheduled_pipeline` его
опрашивает (интервал — `PIPELINE_SCHEDULE_POLL_SECONDS`), а
`watch_stale_pipeline_runs` подчищает зависшие прогоны. CLI
(`core/pipeline/cli.py`) — тонкая обёртка поверх этого сервиса, не
самостоятельная точка входа.

## Архитектура BP-1 (сбор)

Самый крупный пакет; у него **два контура**, и это главная развилка:

1. **Классический** — фиксированные RPA-парсеры под конкретный сайт
   (сегодня только `fedresurs.ru`: обход QRATOR, поиск по ИНН).
2. **Адаптивный** (`src/bp1/adaptive/`) — универсальный движок для всех
   остальных источников: категоризация сайта → выбор стратегии обхода →
   извлечение CSS-селекторов через LLM → кэш адаптеров.

Выбор между ними делает `AdaptiveRunner._get_parser_for_source()`: если для
источника зарегистрирован специализированный парсер в `ParserFactory` — берётся
он, иначе универсальный `AdaptiveBridgeParser`.

### Слои внутри BP-1 — не путать

| Модуль | Уровень | Кто зовёт |
|---|---|---|
| `jobs.py` | публичный API этапа: 4 задания сбора (`collect_source`, `collect_competitor`, `collect_all`, `register_source`) | CLI, Celery |
| `search_task_coverage.py` | синхронизация матрицы «конкурент × источник»: досоздаёт недостающие `SearchTask` без поискового слова, ничего не удаляет и не деактивирует | `jobs.py` |
| `tasks.py` | разбор ОДНОЙ `SearchTask` классическим контуром (`run_parser_async`) | `runner.py`, `celery_tasks.py` |
| `celery_tasks.py` | Celery-задачи пакета (зарегистрированы в `core/celery_app.py` через `include`) | Celery worker/beat |
| `pipeline.py` | точка входа этапа в общий конвейер (`run_bp1`) | `core/pipeline/registry.py` |

Задания `jobs.py` рассчитаны на постановку в очередь: только примитивы на
входе, задание само открывает и закрывает сессию БД и Redis, результат
JSON-сериализуем, создание сущностей идемпотентно («найти или создать») —
повторный запуск (в том числе после ретрая Celery) не плодит дубли.

### Как работает адаптивный сбор

`adaptive/processing/parser/` — пакет (не файл): `core.py` — оркестрация,
`selectors.py`/`content.py`/`pagination.py`/`url_utils.py` — конкретные
шаги извлечения.

Ключевой контур — «категоризация → стратегия → обучение на результате»:

- `SourceClassifier` определяет тип сайта, антибот, CAPTCHA, SPA;
- `AgenticOrchestrator` идёт по лестнице деградации
  `FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL`, пропуская заведомо
  бесполезные шаги (при известной CAPTCHA лёгкие стратегии не пробуются);
- после успеха классификация **переписывается по факту** сработавшей
  стратегии, поэтому следующий прогон не проходит лестницу заново;
- флаги защиты только усиливаются (`False → True`) и не сбрасываются одним
  снимком HTML;
- `AdapterState.fail_count`: если закэшированный адаптер дважды подряд не
  проходит Quality Gate, он сбрасывается и селекторы выводятся заново.

Кэш (`UnifiedCache`) ключуется каноническим hostname, поэтому `lenta.ru`,
`https://lenta.ru/` и `https://www.lenta.ru/news` — один ключ.

## Ловушки

- **`AsyncSession` нельзя использовать конкурентно** — asyncpg падает с
  «another operation is in progress». В `run_all` каждая параллельная задача
  получает свою сессию; переданная снаружи используется только для выборки.
- **`search_task.id` — ключ в Redis** для хэшей дедупликации. Изменение схемы
  затрагивает БД и Redis одновременно.
- **Alembic работает async** и читает `.env` через `core/config.py`: без
  корректного `.env` `alembic upgrade head` падает на подключении. Ruff
  исключает `alembic/` — миграции не линтуются.
- **`settings.bp1_html_dir` / `bp1_raw_dir` — вычисляемые свойства**, а не
  поля настроек: через `.env` задаётся `BP1_DATA_ROOT`. Ключ LLM —
  `LLM_API_KEY` (не `OPENAI_API_KEY`).
- **Pre-commit переформатирует файлы и роняет коммит.** После срабатывания
  `ruff-format` нужно повторно проиндексировать изменённые файлы и создать
  коммит заново.
- **Модуль может требовать настройку, которой нет в `Settings`.** Некоторые
  модули читают `settings.<ключ>` на уровне импорта модуля, а не внутри
  функции — если ключ закомментирован в `core/config.py` (например, ещё не
  включённая интеграция), импорт всего пакета падает `AttributeError`, а не
  только код, который реально этим пользуется. Перед тем как чинить
  непонятную ошибку сбора тестов — проверить, не в этом ли дело.

## Соглашения

- **Комментарии и docstrings — на русском** (конвенция проекта).
- **Nullability из аннотации**: `Mapped[str]` = NOT NULL,
  `Mapped[str | None]` = NULL; не дублировать через `nullable=`.
- **Мягкие удаления**: справочники используют `ActiveMixin`; физически не
  удалять, переключать `is_active`.
- **Redis — кэш, а не хранилище.** История живёт в Postgres; Redis можно
  стереть, данные пересоберутся.
- **Новые модели** регистрировать в `src/db_registry.py` (не трогая
  `alembic/env.py`), иначе autogenerate их не увидит.
- **Новые Celery-задачи** регистрировать в `core/celery_app.py::include`,
  иначе `.delay()` шлёт сообщение, которое некому обработать.
- **Никогда не пушить напрямую в `main` или `develop`** — только через PR.

## Процесс изменений

В репозитории используется spec-driven процесс (`openspec/`): предложения и
задачи лежат в `openspec/changes/<название>/`, утверждённые спецификации —
в `openspec/specs/<область>/`. Крупные изменения оформляются там, а
архив выполненных — в `openspec/changes/archive/`.

Рабочий стиль зафиксирован в [Правила.md](Правила.md): не додумывать за
пользователя и проговаривать допущения; минимальный код без спекулятивных
абстракций; хирургические правки — не «улучшать» соседний код; для
многошаговых задач формулировать проверяемые критерии готовности.
