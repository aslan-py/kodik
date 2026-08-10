# Этот ридми внутренний

- У нас в репозитории две ветки будет Main и Develop
Ветка Main основная, мы туда в  самом конце будем мержить код
Ветка Develop промежуточная, туда смерживать будем нашу ежедневную работу
- В ветку Main мы ничего не комитим. Я её закрою , там должен чистый и рабочий код быть.

## План работы с ветками

### Схема веток и защита

| Ветка | Назначение | Защита |
|-------|-----------|--------|
| `main` | Production (чистый рабочий код) | ✅ PR + 1 одобрение |
| `develop` | Pre-production (интеграция фич) | ✅ PR + 1 одобрение |
| `Oleg/...`, `Zaur/...` | Feature-ветки (личные) | ❌ Без защиты (пушить можно) |

**Важно:** Прямой пуш в `main` и `develop` невозможен. Все коммиты идут через Pull Request с обязательным одобрением - это сделно для того что бы твой код мог посмотреть еще один человек и набраться опыта.

### Процесс разработки

```bash
# 1. Переходишь на develop
git checkout develop

# 2. Запуливаешь свежие изменения
git pull origin develop

# 3. Переходишь на свою ветку (или создаёшь её)
git checkout -b Oleg/my-task
# или если ветка уже существует:
git checkout Oleg/my-task

# ... пишешь код в своей ветке ...

# 4. Закоммитить все изменения
git add .
git commit -m "Описание изменения"

# 5. Запуш изменения
git push origin Oleg/my-task

# Если ты долго ведешь разработку в своей ветке (больше одного дня) и понимаешь
# что другие разработчики в develop могли что то добавить, то выполняешь пункты 1, 2, 3, 4

# 6. Мержишь изменения develop в свою ветку
git merge develop

# Если были конфликты — решаешь их в редакторе, потом:
git add .
git commit -m "Merge develop into Oleg/my-task"

# 7. Пушишь свою ветку на GitHub
git push origin Oleg/my-task
```

Если при merge конфликтов не было — git автоматически создал merge commit, можешь сразу на шаг 6 (push). `git add` и `git commit` нужны только если конфликты были.

Потом создаёшь **Pull Request** на GitHub - будь внимателен, pull request для ветки develop, не перепутай с main, вторая сторона review и мержит в `develop`.

### Процесс review и merge в develop

1. На GitHub создаёшь **Pull Request** (`Oleg/my-task` → `develop`)
2. CI автоматически запускает проверку (ruff, тесты)
3. Второй разработчик **смотрит код и одобряет** (или просит изменения)
4. После одобрения второй разработчик делает **Merge** в `develop` (GitHub автоматически удалит feature-ветку)

### Процесс merge в main

Когда в `develop` накопится достаточно фич и всё стабильно, сливаем `develop` в `main`.

## Настройка окружения разработчика

### 1. Клонировать репозиторий

```bash
git clone <url репозитория>
cd kodik
```

### 2. Установить инструменты разработки

```bash
pip install -r requirements-dev.txt  # Тут чисто линтеры и прекомит
pip install -r requirements.txt
```

#### Браузеры для RPA-сборщиков

`pip install` ставит библиотеку `playwright`, но НЕ сам браузер: это бинарники
(~150 МБ), они качаются отдельной командой и в requirements.txt их положить
нельзя. Без неё RPA-сборщик (`fedresurs`) и `src/run_pipeline.py`
падают при старте браузера.

```bash
python -m playwright install
```

Ставится один раз на машину (в `%LOCALAPPDATA%\ms-playwright`), не в venv —
при пересоздании окружения повторять не нужно. Проверить, что установилось:
`python -m playwright install --dry-run chromium`.

### 3. Активировать pre-commit хуки (один раз)

```bash
pre-commit install
```

После этого при каждом `git commit` автоматически запускаются:
- проверка пробелов, конца файла, YAML/TOML-синтаксиса, маркеров конфликтов
- `ruff` — линтинг + автоисправление
- `ruff-format` — форматирование кода (одинарные кавычки, 80 символов)

### Ручная проверка без коммита

```bash
# Запустить все хуки на всех файлах
pre-commit run --all-files

# Запустить только линтинг
pre-commit run ruff --all-files

# Запустить только форматирование
pre-commit run ruff-format --all-files
```

## Поднятие окружения разработчика (Docker)

### 4. Инициализация контейнеров

```bash
# Копируем шаблон переменных окружения
cp .env.example .env

# Поднимаем все контейнеры (Postgres, Redis, Redis Commander)
docker compose up -d
```

После запуска должны подняться 3 сервиса:
- `kodik_postgres` — основная БД (порт 5432)
- `kodik_redis` — кэш и message broker (порт 6379)
- `kodik_redis_commander` — веб-интерфейс к Redis (порт 8081)

Проверить статус:
```bash
docker compose ps
```

### 5. Просмотр данных в Postgres — DBeaver

Скачать [отсюда](https://dbeaver.io/download/). Дальше: **Новое соединение →
PostgreSQL** и заполнить вкладку «Главное» значениями из своего `.env`:

| Поле в DBeaver | Значение | Откуда берётся |
|---|---|---|
| Хост | `localhost` | `POSTGRES_HOST` |
| Порт | `5432` | `POSTGRES_PORT` |
| База данных | `kodik_db` | `POSTGRES_DB` |
| Пользователь | `admin` | `POSTGRES_USER` |
| Пароль | `password` | `POSTGRES_PASSWORD` |

Галочку «Сохранять пароль» удобно поставить сразу. Итоговая строка подключения
получается такая: `jdbc:postgresql://localhost:5432/kodik_db`.

Если DBeaver предложит скачать драйвер PostgreSQL — соглашайтесь, это разовое
действие. Контейнер `kodik_postgres` при этом должен быть поднят
(`docker compose ps`), иначе будет ошибка «Connection refused».

### 6. Просмотр данных в Redis через Redis Commander

1. Откройте браузер и перейдите на **http://localhost:8081**
2. Никаких кредсов не нужно — интерфейс сразу откроется
3. Видите все ключи Redis, их типы (string, list, hash, set), значения
4. Можете редактировать ключи прямо в UI

### 7. Остановка окружения

```bash
# Остановить контейнеры (данные сохранятся в volumes)
docker compose down

# Остановить и удалить volumes (БД будет чистая при следующем up)
docker compose down -v
```

### Быстрые ссылки для разработчика

Приложение (API и админка) поднимается локально одной командой — контейнер для
него не нужен, только инфраструктура из `docker compose up -d`:

```bash
uvicorn api.main:app --reload
```

| Что | Адрес | Кредсы |
|--------|-----|--------|
| **Swagger** (документация API) | http://localhost:8000/docs | — (не нужны) |
| **Админка** | http://localhost:8000/admin | email + пароль пользователя с ролью `admin` или `analyst` |
| **Redis Commander** (веб-интерфейс к Redis) | http://localhost:8081 | — (не нужны) |
| **Postgres** (подключение из DBeaver или кода) | localhost:5432, база `kodik_db` | admin / password |
| **Redis** (подключение из кода) | localhost:6379 | пароль: password |
| **Схема БД** (dbdiagram) | https://dbdiagram.io/d/6a5a1979067336e1de9aafbb | — (не нужны) |

Кредсы в таблице — значения по умолчанию из `.env.example`. Если вы меняли их в
своём `.env`, подставляйте свои. Redis Commander пароль не спрашивает: он берёт
его сам из `REDIS_PASSWORD` при старте контейнера, а голому клиенту (`redis-cli`,
код приложения) пароль передавать нужно — отсюда разница между двумя строками.

## Навигация по проекту

Подробности каждой темы вынесены в отдельные README, чтобы этот файл не разрастался.

### 1. Справочники и демо-данные

Справочник городов РФ берём отсюда — первоисточник
https://github.com/pensnarik/russian-cities (или более расширенный на всякий
случай https://github.com/arbaev/russia-cities).

Что за файлы лежат в проекте, откуда они взялись и в каком формате —
[`core/scripts/scripts_data/scripts_data_readme.md`](core/scripts/scripts_data/scripts_data_readme.md)

### 2. Наполнение базы данных скриптами

Скрипты сидинга по этапам конвейера и порядок их запуска —
[`core/scripts/SCRIPTS_README.md`](core/scripts/SCRIPTS_README.md)

### 3. Миграции

Работа с alembic — [`alembic/README.md`](alembic/README.md)

Быстрая команда применения миграций, но только после того как поднимешь
контейнер с БД: `alembic upgrade head` — без неё у тебя БД будет пустая.

### 4. API

Эндпоинты, авторизация, роли — [`api/API_README.md`](api/API_README.md)
