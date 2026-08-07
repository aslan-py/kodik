## Why

Зависимости `celery`/`redis` в проекте есть, а самого приложения `Celery()` — нет нигде. BP-1 уже написал рабочую задачу (`src/bp1/celery_tasks.py::run_parser_task`, `@shared_task`) и код, который её диспатчит (`src/bp1/runner.py::run_pipeline(mode='celery')` → `.delay()`), а `README.md` документирует запуск `celery -A src.celery_app worker` — но модуля `src.celery_app` не существует, поэтому `.delay()` сегодня не сработает. При этом Celery нужен не только BP-1: как минимум BP-7 (перенос `source_candidate → source`, «раз в 2 дня» по ТЗ) — тоже кандидат на периодический запуск через Beat. Нужен один общий каркас в `core/`, от которого будут наследоваться задачи всех BP, а не по одному под каждый процесс.

## What Changes

- Новый модуль `core/celery_app.py` — единственный `Celery('kodik', broker=..., backend=...)` на весь проект. `app.conf.timezone` выставлен явно (UTC — тот же стандарт, что уже использует `core/database.py` для `datetime.now(UTC)`). `beat_schedule` заводится **пустым словарём** — структура готова, но записей нет: расписывать под расписание конкретные BP-задачи (когда они появятся) — предмет следующих изменений, не этого.
- В `core/config.py` добавляются настройки для Celery: `celery_broker_db`/`celery_result_backend_db` (отдельные номера БД Redis — **не** тот же `redis_db`, что уже занят под дедуп-хэши BP-1, чтобы ключи очереди и ключи бизнес-логики не путались в одном пространстве) и производные property `celery_broker_url`/`celery_result_backend_url` (по образцу уже существующего `redis_url`).
- **BREAKING для BP-1** (согласовано, не случайная правка): `src/bp1/celery_tasks.py` переключается на импорт общего `app` из `core.celery_app` вместо голого `@shared_task`; три Celery-константы (`CELERY_MAX_RETRIES`, `CELERY_DEFAULT_RETRY_DELAY`, `CELERY_RETRY_BACKOFF_MAX`) переезжают из `src/bp1/constants.py` в общий модуль как дефолты для всех будущих задач; `src/bp1/README.md` обновляется — команда запуска воркера меняется с `celery -A src.celery_app worker` на `celery -A core.celery_app worker`. Существующее поведение `run_parser_task` не меняется, меняется только то, к какому `app` оно привязано.
- `requirements.txt` — добавляется `flower` (веб-панель мониторинга задач/воркеров).
- `.env.example`/`.env` — добавляются `CELERY_BROKER_DB`, `CELERY_RESULT_BACKEND_DB`, `FLOWER_PORT`.

## Non-goals (сознательно вне этого изменения)

- Обёртывание задач BP-2/3/4/5/6/7 в `@shared_task` — следующий этап, по одному BP за раз.
- Заполнение `beat_schedule` реальными записями (интервал BP-7 «раз в 2 дня» зафиксирован в ТЗ, но задачи-цели для расписания пока не существует — регистрировать нечего).
- Уточнение периодичности BP-1/BP-5-дайджеста — не зафиксировано в ТЗ, требует отдельного решения аналитика/PM.
- `docker-compose.yml` не меняется: сервисов `celery-worker`/`celery-beat`/`flower` в нём не будет. В `docker-compose.yml` сегодня нет ни одного `build`-сервиса для самого приложения (только `postgres`/`redis`/`redis-commander` на готовых образах) — заводить Dockerfile ради этого изменения не входит в его рамки. Воркер/beat/flower запускаются локально той же командой, что описана в README (`celery -A core.celery_app worker`), как и само API сегодня. Контейнеризация — предмет отдельного будущего изменения, когда появится Dockerfile приложения (см. design.md).

## Capabilities

### New Capabilities
- `core/celery-infrastructure`: единое Celery-приложение в `core/`, доступное для регистрации задач любого BP, с брокером/бэкендом на отдельных Redis-БД и Beat, готовым принимать расписания.

### Modified Capabilities
(нет — публичного поведения системы формально не существовало, `run_parser_task` был нерабочим)

## Impact

- **Новый модуль:** `core/celery_app.py`.
- **Правится:** `core/config.py` (новые настройки), `src/bp1/celery_tasks.py` (импорт `app`), `src/bp1/constants.py` (три константы уезжают), `src/bp1/README.md` (команда запуска воркера), `requirements.txt`, `.env.example`.
- Код BP-2…BP-7 не затрагивается — эти пайплайны как запускались вручную (`python -m ...`), так и продолжают.
