## 1. Настройки конфигурации

- [ ] 1.1 Добавить в `core/config.py` поля `celery_broker_db`/`celery_result_backend_db` (по образцу существующего `redis_db`), отдельные от `redis_db`
- [ ] 1.2 Добавить в `core/config.py` производные `property` `celery_broker_url`/`celery_result_backend_url` (по образцу существующего `redis_url`)
- [ ] 1.3 Добавить `CELERY_BROKER_DB`, `CELERY_RESULT_BACKEND_DB`, `FLOWER_PORT` в `.env.example` и `.env`

## 2. Celery-приложение

- [ ] 2.1 Создать `core/celery_app.py` с единственным `Celery('kodik', broker=..., backend=...)`, `app.conf.timezone` = UTC
- [ ] 2.2 Задать пустой `beat_schedule = {}` в конфигурации приложения
- [ ] 2.3 Определить дефолты ретрая (`CELERY_MAX_RETRIES`, `CELERY_DEFAULT_RETRY_DELAY`, `CELERY_RETRY_BACKOFF_MAX`) в `core/celery_app.py`

## 3. Перенос BP-1 на общее приложение

- [ ] 3.1 В `src/bp1/celery_tasks.py` заменить голый `@shared_task` на задачу, зарегистрированную через `app` из `core.celery_app`
- [ ] 3.2 Удалить три ретрай-константы из `src/bp1/constants.py` (переехали в `core/celery_app.py` на шаге 2.3)
- [ ] 3.3 Проверить, что `src/bp1/runner.py::run_pipeline(mode='celery')` по-прежнему вызывает `.delay()` без изменений поведения
- [ ] 3.4 Обновить `src/bp1/README.md`: команда запуска воркера `celery -A src.celery_app worker` → `celery -A core.celery_app worker`

## 4. Зависимости и проверка

- [ ] 4.1 Добавить `flower` в `requirements.txt`
- [ ] 4.2 Локально поднять `redis`/`postgres` (`docker-compose up`), затем `celery -A core.celery_app worker` и `celery -A core.celery_app beat` — убедиться, что оба стартуют без ошибок на пустом расписании
- [ ] 4.3 Прогнать `run_pipeline(mode='celery')` и убедиться, что задача реально доходит до воркера и выполняется (закрывает исходный баг: `.delay()` не работал из-за отсутствия `core.celery_app`)
