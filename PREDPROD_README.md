# Этот ридми внутренний

- У нас в репозитории две ветки будет Main и Develop  
Ветка Main основная, мы туда в  самом конце будем мержить код  
Ветка Develop промежуточная, туда смерживать будем нашу ежедневную работу
- В ветку Main мы ничего не комитим. Я её закрою , там должен чистый и рабочий код быть.

## План работы с ветками

В качестве трекера задач используем: https://timon15.kaiten.ru/space/691698/boards

### Схема веток и защита

| Ветка | Назначение | Защита |
|-------|-----------|--------|
| `main` | Production (чистый рабочий код) | ✅ PR + 1 одобрение |
| `develop` | Pre-production (интеграция фич) | ✅ PR + 1 одобрение |
| `Oleg/...`, `Zaur/...` | Feature-ветки (личные) | ❌ Без защиты (пушить можно) |

**Важно:** Прямой пуш в `main` и `develop` невозможен. Все коммиты идут через Pull Request с обязательным одобрением.

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

# 5. Мержишь develop в свою ветку
git merge develop

# Если были конфликты — решаешь их в редакторе, потом:
git add .
git commit -m "Merge develop into Oleg/my-task"

# 6. Пушишь свою ветку на GitHub
git push origin Oleg/my-task
```

Если при merge конфликтов не было — git автоматически создал merge commit, можешь сразу на шаг 6 (push). `git add` и `git commit` нужны только если конфликты были.

Потом создаёшь **Pull Request** на GitHub, вторая сторона review и мержит в `develop`.

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

# Поднимаем все контейнеры (Postgres, Redis, pgAdmin, Redis Commander)
docker compose up -d
```

После запуска должны подняться 4 сервиса:
- `kodik_postgres` — основная БД (порт 5432)
- `kodik_redis` — кэш и message broker (порт 6379)
- `kodik_pgadmin` — веб-интерфейс к Postgres (порт 5050)
- `kodik_redis_commander` — веб-интерфейс к Redis (порт 8081)

Проверить статус:
```bash
docker compose ps
```

### 5. Просмотр данных в Postgres через pgAdmin

1. Откройте браузер и перейдите на **http://localhost:5050**
2. Введите кредсы (из `.env`):
   - Email: `admin@main.ru`
   - Пароль: `password`
3. После входа нажмите **Add New Server** в левой панели
4. На вкладке **General** введите имя: `kodik_postgres`
5. На вкладке **Connection** введите:
   - Host name: `postgres` (имя сервиса в docker-compose)
   - Port: `5432`
   - Username: `admin` (POSTGRES_USER из `.env`)
   - Password: `password` (POSTGRES_PASSWORD из `.env`)
   - Database: `kodik_db` (POSTGRES_DB из `.env`)
6. Нажмите **Save** — сервер добавлен, можете смотреть таблицы и выполнять SQL-запросы

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

| Сервис | URL | Кредсы |
|--------|-----|--------|
| **pgAdmin** | http://localhost:5050 | admin@main.ru / password |
| **Redis Commander** | http://localhost:8081 | — (не нужны) |
| **Postgres** (прямое подключение) | localhost:5432 | admin / password |
| **Redis** (прямое подключение) | localhost:6379 | пароль: password |

### По работе с БД и миграциями смотри alembic\README.md
- Быстрая команда применения миграций, но только после того как поднимешь контейнер с БД `alembic upgrade head` - без неё у тебя БД будут пустыми