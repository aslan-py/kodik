## Why

Технические логи конвейера доступны только как поток stdout контейнеров и Flower не объясняет работу BP1—BP7. Нужен постоянный поиск и просмотр логов без создания новых таблиц PostgreSQL и без изменения бизнес-данных.

## What Changes

- Добавить Grafana Alloy, Loki и Grafana в Docker Compose для сбора, хранения и просмотра stdout-логов контейнеров.
- Обогатить ключевые логи конвейера `run_id`, этапом, статусом и краткой сводкой результата.
- Подготовить в Grafana готовый источник Loki и дашборд для API, Celery Beat, основного worker и BP1 worker.
- Добавить в админку ссылку на внешний технический журнал Grafana; сами логи и новые модели в PostgreSQL не создаются.

## Capabilities

### New Capabilities

- `core/pipeline-run-events`: контекстные технические записи жизненного цикла прогона в stdout.

### Modified Capabilities

- `admin/pipeline-control`: экран пайплайна даёт переход к внешнему техническому журналу.
- `core/celery-pipeline-orchestration`: оркестратор выводит записи с контекстом прогона и этапа.

## Impact

Затрагиваются Docker Compose, конфигурация Alloy/Loki/Grafana, стандартный logging, оркестратор и админка. PostgreSQL, `RawItem`, API журнала и миграции не изменяются.
