## ADDED Requirements

### Requirement: Технические события хранятся во внешнем Loki
Система SHALL отправлять stdout контейнеров в Loki через Grafana Alloy. Хранилище MUST быть отдельным Docker volume и не использовать PostgreSQL, миграции или `RawItem`.

#### Scenario: Сервис пишет в stdout
- **WHEN** API, Beat или worker пишет строку лога
- **THEN** Alloy передаёт её в Loki с метками Compose-сервиса и контейнера

### Requirement: Grafana предоставляет готовый просмотр логов
Grafana SHALL иметь заранее настроенный datasource Loki и дашборд для API, Beat, основного worker и BP1 worker.

#### Scenario: Администратор расследует запуск
- **WHEN** администратор открывает Grafana
- **THEN** он может отфильтровать логи по сервису и найти записи по `run_id`
