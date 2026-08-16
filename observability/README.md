# Технические логи

Grafana открывается по `http://localhost:3001` (или адресу из `GRAFANA_URL`). Учётные данные задаются в `.env`: `GRAFANA_ADMIN_USER` и `GRAFANA_ADMIN_PASSWORD`.

После входа откройте дашборд **Kodik / Kodik: технические логи**. Выберите сервис (`api`, `celery-beat`, `celery-worker`, `celery-worker-bp1`) и вставьте в поле поиска `run_id` из ответа на запуск.

## Что где смотреть

- Grafana — поиск и история stdout-логов контейнеров за 14 дней.
- Flower — состояние и статистика Celery-задач; это не журнал процесса.
- `docker compose logs -f <сервис>` — живой поток конкретного контейнера; он остаётся доступен как прежде.

Loki не использует PostgreSQL и не создаёт миграции. Логи лежат в отдельном Docker volume `loki_data`; срок хранения — 14 дней.
