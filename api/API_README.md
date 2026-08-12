# API: FastAPI-слой поверх конвейера BP-1…BP-5

Веб-слой для просмотра/правки витрины (`showcase_event`, BP-4) и
JWT-авторизации пользователей с ролями. Общий пакет `api/` в корне —
не привязан к одному BP, модели переиспользует из `src/bp3`, `src/bp4`,
`src/bp5`. Детали решений и почему сделано именно так — `FASTAPI_PLAN.md`
в этой же папке.

---

## Запуск

Нужна поднятая БД (`docker-compose up -d`) и накаченные миграции:

```bash
alembic upgrade head
python -m api.main
```

Требуемые переменные окружения (`.env`, см. `.env.example`):
`API_PORT`, `JWT_SECRET_KEY`, `JWT_EXPIRE_MINUTES` — добавлены к уже существующим
Postgres/Redis/Mail/Telegram настройкам.

Порт меняется в одном месте — `API_PORT` в `.env`. Команда
`python -m api.main` читает его через `core.config.settings`; например,
при `API_PORT=8001` Swagger доступен на `http://127.0.0.1:8001/docs`.

`api/main.py` — только сборка приложения (`FastAPI()` + `include_router`).
Пайплайны (BP-2/BP-4/BP-5) сюда не переехали и не переедут — это отдельный
процесс, Celery+Beat (см. `FASTAPI_PLAN.md`, п.5).

## Структура `api/`

```
api/
  main.py               # FastAPI() + tags_metadata + include_router(main_router)
  routers.py             # единая точка сборки: здесь и только здесь prefix=/tags=
  dependencies.py         # SessionDep, get_current_user, require_role(...)
  security.py             # хэш пароля (bcrypt), JWT (create/decode_access_token)
  responses.py             # пресеты responses={...} для документации ошибок в Swagger
  tags_metadata.py          # порядок и описания тегов Swagger
  endpoints/                # сами эндпоинты (bare APIRouter(), без prefix/tags)
    auth.py, users.py, showcase.py
  validators/                # чистые Pydantic-валидаторы полей (без похода в БД)
    users.py                  # CustomPassword — сложность пароля
    showcase.py                 # require_at_least_one_field — запрет пустого PATCH
  crud/                        # доступ к БД (UserCRUD, ShowcaseCRUD)
  schemas/                      # Pydantic-схемы запросов/ответов + error.py (ErrorDetail)
```

`endpoints/*.py` содержат только сами роуты — какой у чего префикс и тег,
видно в одном месте (`routers.py`), не открывая каждый файл. DB-проверки
уникальности (email/telegram_id — требуют сессию) остаются в
`crud/users.py`, а не в `validators/` — там только синхронные проверки
формата поля.

## Админка

`http://127.0.0.1:8001/admin` — веб-интерфейс над справочниками и данными
конвейера (FastAdmin). Живёт в **этом же** процессе `uvicorn`: отдельный
сервер и контейнер не нужны. Вход по email+паролю, роли `admin`/`analyst`.
Подробности — **[ADMIN_README.md](ADMIN_README.md)**.

## Документация API

- Swagger UI: `http://127.0.0.1:8001/docs`
- ReDoc: `http://127.0.0.1:8001/redoc`
- Сырая OpenAPI-схема: `http://127.0.0.1:8001/openapi.json`

**Кнопка Authorize в Swagger.** Схема авторизации — простой HTTP Bearer
(`HTTPBearer`, `api/security.py`), без своего OAuth2-flow: в диалоге
Authorize только одно поле `Value`, туда вставляется голый токен (без
слова `Bearer` — Swagger сам подставит префикс в заголовок).

1. Выполнить `POST /auth/login` (через «Try it out» или `curl`), скопировать
   `access_token` из ответа.
2. Нажать «Authorize» (значок замка справа сверху), вставить токен в поле
   `Value`, нажать «Authorize» → «Close». Дальше все запросы из Swagger
   идут с этим токеном автоматически.

(Раньше здесь стоял `OAuth2PasswordBearer` — он декларирует полноценный
OAuth2-password-flow, из-за чего Authorize показывал поля username/
password и сам пытался залогиниться form-data запросом на `/auth/login`,
а тот принимает JSON — поэтому окно молча падало с 422. `HTTPBearer` этой
проблемы не имеет.)

**Ошибки в Swagger.** Кастомных exception-хэндлеров нет — формат ответа
на ошибку остаётся стандартным для FastAPI: `{"detail": "..."}`. Но
Swagger по умолчанию документирует только `200` и `422` — коды, которые
эндпоинт бросает вручную (`401`/`403`/`404`/`409`), в схему не попадают,
пока не объявлены явно. `api/responses.py` — пресеты `responses={...}`
именно под это: у каждого эндпоинта в `api/endpoints/*.py` в Swagger
теперь видны все реальные коды ошибок с описанием и примером тела
(`ErrorDetail`, `api/schemas/error.py`).

Отдельный случай — `422 {"detail": [{"type": "json_invalid", ...}]}` с
`"msg": "JSON decode error"` и `"error": "Expecting ',' delimiter"`. Это
не наша валидация — тело запроса ещё даже не дошло до Pydantic-схемы,
это встроенный в FastAPI разбор синтаксически невалидного JSON (например,
пропущена запятая между полями). Сообщение и позиция символа — то, что
и должно быть в такой ситуации, отдельно причёсывать не нужно.

---

## Роли и права

`role` (`core.enums.UserRole`) — это НЕ отдел (`department_id` в `User`
справочный, к рассылке не привязан, см. `FASTAPI_PLAN.md`, п.4):

| Роль | Доступ |
|------|--------|
| `pending` | только что зарегистрировался. Доступен один эндпоинт — `GET /users/me` |
| `viewer` | + чтение витрины (`GET /showcase`, `GET /showcase/{id}`) |
| `analyst` | + правка витрины (`PATCH /showcase/{id}`), подтверждение `pending` → `viewer`/`analyst` |
| `admin` | + управление пользователями/справочниками |

Новый пользователь всегда получает `role=pending` — поднять до `viewer`/
`analyst`/`admin` может только `analyst` или `admin` через
`PATCH /users/{id}/role`. Своего первого админа нужно поднять руками в БД
(`UPDATE "user" SET role='admin' WHERE id=...`) — эндпоинта для этого нет
намеренно, чтобы это не мог сделать сам себе никто через API.

---

## Эндпоинты

### `auth` — регистрация и логин

| Метод | Путь | Доступ | Что делает |
|-------|------|--------|-----------|
| POST | `/auth/register` | публично | Создаёт `User` с `role=pending`. Хэширует пароль (bcrypt). `email` и (если указан) `telegram_id` проверяются на уникальность до вставки — иначе `409` |
| POST | `/auth/login` | публично | Проверяет email+пароль, выдаёт JWT (`access_token`, `exp` через `JWT_EXPIRE_MINUTES`) |

**Требования к паролю при регистрации** (`api/validators/users.py::validate_password`):
не короче 8 символов, хотя бы одна заглавная буква, строчная буква и цифра.
Проверяется только при `POST /auth/register` — `POST /auth/login` пароль
не валидирует по формату (иначе логин отвалился бы для пользователя, чей
пароль завели до появления этого правила), только сверяет с хэшем.

### `users`

| Метод | Путь | Доступ | Что делает |
|-------|------|--------|-----------|
| GET | `/users/me` | любой залогиненный (даже `pending`) | Профиль текущего пользователя |
| GET | `/users` | `analyst`/`admin` | Список всех пользователей — отсюда видно, кого нужно подтвердить |
| PATCH | `/users/{id}/role` | `analyst`/`admin` | Меняет роль пользователя (подтверждение `pending` → `viewer`/`analyst`, назначение `admin`) |

### `showcase` — витрина BP-4

| Метод | Путь | Доступ | Что делает |
|-------|------|--------|-----------|
| GET | `/showcase` | `viewer`/`analyst`/`admin` | Список строк витрины (`limit`/`offset`, сортировка по `published_at`) |
| GET | `/showcase/{id}` | `viewer`/`analyst`/`admin` | Одна строка витрины |
| PATCH | `/showcase/{id}` | `analyst`/`admin` | Правка разметки (см. ниже) |

**`PATCH /showcase/{id}` не пишет напрямую в `showcase_event`.** Витрина —
производная таблица (`ABOUT.md`, BP-4 п.5): источник правды для
`priority`/`category_id`/`tonality`/`action`/`deadline`/`department_id`/
`comment` — это `categorized_event`. Эндпоинт в одной транзакции:

1. пишет переданные поля в `categorized_event` (источник правды —
   следующий прогон BP-4 не затрёт правку и не разъедется с ней);
2. тем же значением зеркалит `showcase_event` (те же подписи, что и
   `src/bp4/pipeline.py::build_showcase_row` — «p1» → «П1» и т.п.),
   выставляя `updated_at = datetime.now(UTC)`.

Тело запроса — только переданные поля (partial update), поля со значением
`null` в JSON корректно очищают колонку (`comment: null` → комментарий
стирается), а отсутствующее в теле поле не трогается вовсе. Факты
(`title`, `media`, `region`, `competitor`, `source_url`, координаты) через
этот эндпоинт не редактируются — они приходят из `normalized_item`, а не
из разметки.

Пустое тело (`{}`) — `422` (`api/validators/showcase.py::
require_at_least_one_field`): без этой проверки пустой PATCH тихо
проходил бы и превращался в no-op (`ShowcaseCRUD.update()` не находит
изменений через `exclude_unset`), а `200` без единого изменённого поля
скорее вводит в заблуждение, чем помогает.

---

## Регистрация и telegram_id

`telegram_id` в `POST /auth/register` — необязательное поле. Если не
указать, пользователь работает в системе (логин, `GET /users/me`, чтение/
правка витрины по роли), но алерты BP-5 до момента, пока `telegram_id` не
появится в `User`, физически может доставить только `email`-канал.

Ошибок в BP-5 из-за отсутствия `telegram_id` не будет:
- в тестовом режиме (`TRUE_ALERTING=False`) BP-5 всегда шлёт на
  `TEST_EMAIL`/`TEST_TG` из `.env`, `telegram_id` конкретного пользователя
  вообще не читается;
- в боевом режиме (`TRUE_ALERTING=True`) `telegram_id` читается, только
  если для этого пользователя в `routing_rule` есть строка на канал
  `telegram`. Если её нет — телеграм для него не пробуется, всё ок. Если
  такая строка есть, а `telegram_id` не задан — попытка отправки упадёт
  (`aiogram` не примет `chat_id=None`), но `src/bp5/pipeline.py` ловит
  исключение и помечает именно эту строку `alert.status=failed` с текстом
  ошибки — остальные алерты (в т.ч. email этому же пользователю) уходят
  как обычно, весь прогон BP-5 не падает.

На данный момент это решается на уровне аналитика, который заполняет
`routing_rule`: не заводить пользователя без `telegram_id` на канал
`telegram`. Проверки на уровне БД/API, что для строки `routing_rule` с
`channel=telegram` у `user_id` обязательно есть `telegram_id`, пока нет —
если понадобится, это отдельная небольшая доработка (валидация в
CRUD `routing_rule` или CHECK на уровне БД).

Привязать `telegram_id` после регистрации отдельным эндпоинтом (например,
`PATCH /users/me`) сейчас нельзя — такого эндпоинта ещё нет. Скажи, если
он нужен.
