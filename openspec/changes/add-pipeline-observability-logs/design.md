## Context

См. proposal.md. Приложение уже пишет в stdout; Docker Compose управляет API, worker, BP1 worker и Beat. Пользователь явно исключил отдельное хранение логов в PostgreSQL.

## Goals / Non-Goals

**Goals:** собрать stdout всех сервисов, хранить и искать его в отдельном Loki volume, дать Grafana с преднастроенным дашбордом и искать запуск по `run_id`.

**Non-Goals:** не создавать миграции, модели, API журнала или журнал в админке; не менять `RawItem`; не заменять Flower.

## Decisions

### Grafana Alloy → Loki → Grafana

Alloy читает Docker stdout через Docker socket, добавляет метки Compose service/container и отправляет в Loki. Loki хранит данные в отдельном Docker volume. Grafana имеет provisioned Loki datasource и дашборд. Так `docker compose logs` продолжает работать, а Grafana становится историческим интерфейсом.

### Контекст — logfmt в ключевых записях

Новые записи orchestration выводятся как безопасный logfmt: `pipeline_event=... run_id=... stage=... status=...`. Это не требует переделывать все существующие логгеры и позволяет искать по тексту/полям в Grafana.

### Админка не проксирует Loki

В админке остаётся внешняя ссылка на Grafana из конфигурации. Доступ к Grafana задаётся её собственной учётной записью; API приложения не получает права читать весь поток логов.

## Risks / Trade-offs

- [Docker socket даёт Alloy доступ к метаданным контейнеров] → Alloy запускается только внутри локального/защищённого Compose-стека и не публикует свой порт.
- [Loki недоступен] → работа приложения и stdout не блокируются; `docker compose logs` остаётся запасным способом диагностики.
- [Рост объёма] → задать retention и отдельный volume Loki.

## Migration Plan

1. Добавить сервисы и конфигурации без миграций БД.
2. Пересоздать Compose-стек пользователем.
3. Открыть Grafana и проверить дашборд после одного прогона.
