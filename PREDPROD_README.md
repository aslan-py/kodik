# PREDPROD: запуск Docker Compose

## 1. Файл `.env`

```env
POSTGRES_USER=admin
POSTGRES_PASSWORD=<ваше_значение>
POSTGRES_DB=kodik_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<ваше_значение>
TRUE_ALERTING=True
TEST_EMAIL=lujayka@mail.ru
TEST_TG=302355541
MAIL_USERNAME=booking_no_reply@rambler.ru
MAIL_PASSWORD=<ваше_значение>
MAIL_FROM=booking_no_reply@rambler.ru
MAIL_FROM_NAME=Booking
MAIL_SERVER=smtp.rambler.ru
MAIL_PORT=465
MAIL_STARTTLS=False
MAIL_SSL_TLS=True
MAIL_USE_CREDENTIALS=True
MAIL_VALIDATE_CERTS=True
TELEGRAM_BOT_TOKEN=<ваше_значение>
CELERY_BROKER_DB=1
CELERY_RESULT_BACKEND_DB=2
CELERY_WORKER_CONCURRENCY=2
CELERY_BP1_WORKER_CONCURRENCY=1
CELERY_TASK_SOFT_TIME_LIMIT_SECONDS=900
CELERY_TASK_TIME_LIMIT_SECONDS=960
CELERY_TASK_MAX_RETRIES=3
CELERY_TASK_DEFAULT_RETRY_DELAY_SECONDS=60
CELERY_TASK_RETRY_BACKOFF_MAX_SECONDS=600
PIPELINE_SCHEDULE_ENABLED=False
PIPELINE_SCHEDULE_CRON=0 8 * * *
PIPELINE_SCHEDULE_TIMEZONE=Europe/Moscow
PIPELINE_SCHEDULE_POLL_SECONDS=60
PIPELINE_RUN_STALE_TIMEOUT_SECONDS=1800
FLOWER_BASIC_AUTH=admin:admin
FLOWER_PORT=5555
API_HOST=127.0.0.1
API_PORT=8001
APP_TITLE=Конкурентная разведка
DESCRIPTION=API управления проектом конкурентной разведки
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
JWT_SECRET_KEY=<сгенерируйте_значение>
JWT_EXPIRE_MINUTES=60
PASSWORD_RESET_CODE_EXPIRE_MINUTES=10
ADMIN_SITE_NAME=Кодик — админка
ADMIN_LANGUAGE=ru
ADMIN_SECRET_KEY=
ADMIN_SESSION_COOKIE_SECURE=False
TRUE_PARSING=True
BP1_DATA_ROOT=./src/bp1/data
LLM_API_KEY=ТУТ от дипсика
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
BP1_MAX_NEWS_PER_SOURCE=3
BP1_MIN_ARTICLE_TEXT_LENGTH=100
BP1_MIN_FULL_ARTICLE_TEXT_LENGTH=300
BP1_MAX_TAIL_FETCH_ATTEMPTS=3
BP1_MIN_CONTENT_LENGTH=300
BP1_PARSE_TIMEOUT_MS=60000
BP1_MAX_CONCURRENT_TASKS=5
BP1_ARTICLE_FETCH_TIMEOUT_SECONDS=20.0
BP1_MAX_CONCURRENT_FETCHES=3
BP1_ADAPTER_TTL_SECONDS=604800
BP1_CLASSIFICATION_TTL_SECONDS=604800
BP1_ARTICLE_TEXT_TTL_SECONDS=604800
BP1_ADAPTIVE_MODE=adaptive
BP1_HEADLESS=True
SOURCE_CIRCUIT_TTL_SECONDS=200
SOURCE_DISABLE_THRESHOLD=3
OPENROUTER_API_KEY= тут от опенроутера
TAVILY_API_KEY= тут от тавити
BP3_MODEL=openai/gpt-4o
BP3_SEARCH_MAX_RESULTS=4
BP3_SEARCH_DEPTH=basic
BP3_SEARCH_TIME_RANGE=week
BP3_LLM_BASE_URL=https://openrouter.ai/api/v1
BP3_LLM_TEMPERATURE=0
BP3_LLM_MAX_TOKENS=4096
DEEPSEEK_TOKEN=Дипсик токен
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
SOURCE_CANDIDATE_SCORE_THRESHOLD=0.5
FRONTEND_PORT=3000
REDIS_COMMANDER_PORT=8081
GRAFANA_PORT=3001
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<ваше_значение>
GRAFANA_URL=http://localhost:3001
```

## 2. Запуск контейнеров

```powershell
docker compose up -d --build
```

## 3. Интерфейсы

| Интерфейс | Адрес |
|---|---|
| Frontend | http://localhost:3000 |
| Админка | http://localhost:8001/admin |
| API Swagger | http://localhost:8001/docs |
| API ReDoc | http://localhost:8001/redoc |
| Flower | http://localhost:5555 |
| Redis Commander | http://localhost:8081 |
| Grafana | http://localhost:3001 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## 4. Запуск процесса через админку без Celery Beat

Админка: http://localhost:8001/admin

Раздел: **Пайплайн**.

Для ручного запуска:

1. Заполнить и включить нужные записи в справочниках.
2. Выбрать этап или **Запустить всё**.
3. Для BP-1 включить переключатель **реальный сбор**.
4. Нажать **Выполнить действие**.
5. Полученный `run_id` смотреть в Flower или Grafana.

Для ручного запуска нужны worker-контейнеры `celery-worker` и `celery-worker-bp1`. Celery Beat не нужен.

## 5. Таблицы, необходимые этапам

| Этап | Необходимые таблицы |
|---|---|
| BP-1 | `competitor`, `source`, `search_task`; `trigger` — если используется поисковый триггер |
| BP-2 | `raw_item` |
| BP-3 | `normalized_item` |
| BP-4 | `categorized_event` |
| BP-5 | `showcase_event` |
| BP-6 | `showcase_event` |
| BP-7 | `source_candidate` — очередь кандидатов может быть пустой |

Справочники/данные для BP-1: `competitor`, `source`, `trigger` (необязательно); города — `core/scripts/scripts_data/cities.json`.

## 6. Настройка Celery Beat в админке

Раздел **Пайплайн** → действие **Сохранить расписание**.

Заполнить:

- переключатель **включено**;
- поле **крон**;
- часовой пояс: `Europe/Moscow`.

Значения поля **крон**:

| Запуск | Крон |
|---|---|
| Каждые 5 минут | `*/5 * * * *` |
| Каждые 10 минут | `*/10 * * * *` |
| Каждый день в 19:00 | `0 19 * * *` |

После сохранения должны работать `celery-beat`, `celery-worker` и `celery-worker-bp1`.
