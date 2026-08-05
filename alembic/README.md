# Alembic — миграции базы данных

Управление схемой PostgreSQL для проекта **Кодик**.
Используется asyncpg + SQLAlchemy 2.0 async.

## Основные команды

Запускать из корня проекта (при активном `.env` и поднятой БД).

| Действие | Команда |
|---|---|
| Создать миграцию по моделям | `alembic revision --autogenerate -m "описание"` |
| Применить все миграции | `alembic upgrade head` |
| Откатить последнюю | `alembic downgrade -1` |
| Откатить до версии | `alembic downgrade <revision_id>` |
| Текущая версия БД | `alembic current` |
| История миграций | `alembic history` |

## Структура

```
alembic/
  env.py           — конфигурация: подключает settings.database_url и Base.metadata
  README.md        — этот файл
  script.py.mako   — шаблон генерации файлов миграций
  versions/        — файлы миграций (коммитить в git!)
```

## Как добавить модели нового BP

1. Создать `src/bpN/models.py` с моделями.
2. Реэкспортировать их из `src/bpN/__init__.py`.
3. Добавить одну строку в `src/db_registry.py`:
   ```python
   import src.bpN  # noqa: F401
   ```
4. Запустить `alembic revision --autogenerate -m "add bpN tables"`.

## Примечания

- URL базы данных берётся из переменных `POSTGRES_*` в `.env` через `core/config.py`.
  Строка `sqlalchemy.url` в `alembic.ini` намеренно пустая — переопределяется в `env.py`.
- Файлы в `versions/` — это история изменений схемы, их **обязательно коммитить**.
- Миграции описывают **только схему** (таблицы, индексы, enum-типы). Сидинг
  данных в миграции НЕ кладём — для тестовых данных есть отдельные скрипты
  `core/scripts/seed_all.py` (залить всё) и `core/scripts/clear_data.py`
  (очистить данные, справочники сохранить).
