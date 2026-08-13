## 1. Модели и конфигурация

- [ ] 1.1 Добавить enum'ы и модели `PipelineRun`, `PipelineStageRun`, `PipelineSchedule` с индексами, связями, timestamps и сериализуемыми результатами/ошибками
- [ ] 1.2 Добавить атомарное ограничение `active_slot` для единственного активного прогона и уникальность этапа внутри прогона
- [ ] 1.3 Создать и проверить Alembic-миграцию новых таблиц, enum'ов, индексов и начальной singleton-записи расписания
- [ ] 1.4 Добавить настройки env для cron/enabled/timezone, poll/stale timeout, worker concurrency/time limits и Flower credentials
- [ ] 1.5 Обновить `.env.example` с безопасными defaults и явными обязательными секретами без изменения реального `.env`
- [ ] 1.6 Реализовать единый вычислитель effective schedule, источников `env`/`admin`, последнего и следующего cron slot с IANA timezone

## 2. Celery app и маршрутизация

- [ ] 2.1 Зарегистрировать модули задач всех BP и orchestration tasks в единственном `core.celery_app`
- [ ] 2.2 Настроить очереди `pipeline.control`, `pipeline.bp1`, `pipeline.stages` и явные task routes
- [ ] 2.3 Настроить JSON serialization, late acknowledgements, prefetch, retry defaults и soft/hard time limits из config
- [ ] 2.4 Проверить, что существующий BP1 parser task использует общий Celery app и маршрут `pipeline.bp1`
- [ ] 2.5 Добавить диагностическую проверку зарегистрированных задач и маршрутов, падающую при отсутствии любого BP1—BP7 wrapper

## 3. Оркестрация прогонов

- [ ] 3.1 Реализовать сервис атомарного создания одиночного/полного прогона со stage rows, снимком параметров, источником и инициатором
- [ ] 3.2 Реализовать конфликт активного прогона с возвратом его `run_id` для всех entrypoints
- [ ] 3.3 Ввести типизированные ошибки предусловий, бизнес-логики и временной инфраструктуры вокруг существующего runner
- [ ] 3.4 Реализовать идемпотентный Celery wrapper этапа с блокировкой stage-row, heartbeat, task id, attempts и сохранением result/error
- [ ] 3.5 Реализовать одиночный canvas из stage wrapper и финализатора с маршрутом соответствующего BP
- [ ] 3.6 Реализовать полный `chain` BP1—BP7, передающий success/failure envelope и продолжающийся после ожидаемой ошибки этапа
- [ ] 3.7 Реализовать финализатор итоговых статусов `succeeded`, `partial_failed`, `failed` и освобождения `active_slot`
- [ ] 3.8 Реализовать errback и watchdog зависших прогонов с терминальным статусом `stale` и диагностической причиной
- [ ] 3.9 Обработать ошибку публикации canvas после DB commit с освобождением slot и наблюдаемым статусом `failed`
- [ ] 3.10 Добавить безопасный reconciler для `queued` прогонов без task id, не допускающий повторного запуска завершённых этапов

## 4. Celery Beat и динамическое расписание

- [ ] 4.1 Добавить статическую Beat-запись dispatcher с интервалом `PIPELINE_SCHEDULE_POLL_SECONDS`
- [ ] 4.2 Реализовать транзакционное резервирование UTC cron slot через singleton schedule-row без дубликатов
- [ ] 4.3 Реализовать запуск полного pipeline от Beat и наблюдаемую запись пропуска, если pipeline занят
- [ ] 4.4 Реализовать runtime override enabled/cron/timezone и атомарный сброс к env defaults
- [ ] 4.5 Добавить тесты выключенного расписания, смены override без рестарта, повторного poll и timezone/DST границ

## 5. Pipeline API

- [ ] 5.1 Добавить схемы запросов/ответов прогона, этапов, истории, конфликта и effective schedule
- [ ] 5.2 Реализовать `POST /pipeline/runs` с HTTP 202 и `POST /pipeline/stages/{stage}/runs` с валидацией BP1—BP7 и параметров этапа
- [ ] 5.3 Реализовать пагинированный `GET /pipeline/runs` и подробный `GET /pipeline/runs/{run_id}` из PostgreSQL
- [ ] 5.4 Реализовать `GET /pipeline/schedule` с источниками значений, `last_scheduled_for` и `next_run_at`
- [ ] 5.5 Реализовать `PATCH /pipeline/schedule` для частичного override и явного reset с проверкой cron/timezone
- [ ] 5.6 Подключить существующую ролевую модель: чтение для viewer+, запуск и изменение для analyst/admin
- [ ] 5.7 Добавить API-тесты 202/404/409/422/403, пагинации, параметров BP1/BP2 и schedule override/reset

## 6. Админка и CLI

- [ ] 6.1 Перевести семь кнопок этапов и кнопку полного pipeline с прямого runner на общий orchestration service
- [ ] 6.2 Показывать после постановки `run_id`, статус `queued`, конфликт активного прогона и ссылку на детали без ожидания worker'а
- [ ] 6.3 Сохранить per-run переключатели reparse и true/stub implementation в снимке параметров
- [ ] 6.4 Добавить на верхний Pipeline Dashboard карточку effective schedule с enabled/cron/timezone, источниками, next run, save и reset
- [ ] 6.5 Добавить список последних ручных/плановых прогонов и детали упорядоченных BP1—BP7 с автообновлением активного статуса
- [ ] 6.6 Согласовать экран с `reorganize-admin-navigation`, не создавая дублирующий раздел Pipeline
- [ ] 6.7 Перевести production CLI на enqueue и вывод `run_id`, оставив прямой runner только за явно названным diagnostic флагом/командой
- [ ] 6.8 Добавить тесты админских действий, формы расписания, прав доступа и сохранения переключателей запуска

## 7. Docker и Flower

- [ ] 7.1 Создать общий Dockerfile приложения с runtime-зависимостями и Playwright/browser dependencies для BP1 worker
- [ ] 7.2 Расширить Compose сервисами `api`, общим Celery worker, BP1 worker, singleton `celery-beat` и `flower`
- [ ] 7.3 Настроить контейнерные адреса PostgreSQL/Redis, зависимости старта, restart policy, healthchecks, volumes и явные подписки worker'ов на очереди
- [ ] 7.4 Настроить Flower на общий Celery app, обязательную basic auth и внутренний/локальный порт без открытых production credentials
- [ ] 7.5 Проверить `docker compose config` и healthchecks всех сервисов на чистой конфигурации из `.env.example`

## 8. Сквозная проверка и документация

- [ ] 8.1 Добавить unit-тесты моделей, переходов статусов, unique active slot, idempotent redelivery и retry-классификации
- [ ] 8.2 Добавить eager-mode тест полного chain: успех всех BP и ожидаемая ошибка среднего BP с продолжением следующих этапов
- [ ] 8.3 Добавить integration-тест с Redis/PostgreSQL для маршрутов очередей, task registration, task ids и блокировки конкурирующих запусков
- [ ] 8.4 Выполнить Compose smoke test одиночного BP, полного BP1—BP7, рестарта worker'а, watchdog и сохранения истории
- [ ] 8.5 Выполнить smoke test планового запуска, изменения/сброса расписания из API и админки и отсутствия дублированного cron slot
- [ ] 8.6 Проверить Flower auth, видимость обоих worker'ов/трёх очередей и отсутствие секретов в task arguments
- [ ] 8.7 Обновить эксплуатационную документацию: процессы запускаются отдельно, команды Compose/локального запуска, диагностика очередей, rollback и защита Flower через TLS proxy
- [ ] 8.8 Запустить полный проектный test suite и строгую OpenSpec-валидацию, зафиксировать фактические команды и результаты
