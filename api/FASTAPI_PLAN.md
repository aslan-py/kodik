# FastAPI-слой: структура api/, авторизация, синхронизация витрины, пайплайны

Черновик решений, обсуждённых 2026-08-02. Продолжить реализацию отсюда.

## Контекст

Нужен рабочий web-слой поверх готового конвейера BP-1…BP-5: сначала API для просмотра/правки
витрины (`showcase_event`) и JWT-авторизация пользователей с ролями. Согласовано: общий слой —
новый пакет `api/` в корне, пользователь для логина — переиспользуем `src/bp5/models.py::User`.

---

## 1. `SessionDep` — где использовать, а где нет

`SessionDep = Annotated[AsyncSession, Depends(get_async_session)]` работает **только** внутри
FastAPI: `Depends(...)` резолвится DI-контейнером FastAPI на каждый HTTP-запрос. В пайплайнах,
Celery-тасках и скриптах (`src/bp2/pipeline.py`, `src/bp1/celery_tasks.py`, `core/scripts/stages/*`)
никакого FastAPI-контекста нет — `Depends` там просто не будет вызван, это не рабочий способ
получить сессию. **Там и дальше нужен `AsyncSessionLocal` напрямую** (`async with AsyncSessionLocal() as session:`), как сейчас и сделано.

Дополнительно: сам `core/database.py` в докстринге (строки 8-12) изначально задумывался
framework-agnostic — «FastAPI-обвязка (Depends) добавляется отдельно в `api/deps.py`», чтобы
парсеры/Celery-воркеры не тянули `fastapi` как зависимость. Раз теперь заводим `api/`, стоит
перенести `SessionDep` (и `from fastapi import Depends`) из `core/database.py` в новый `api/deps.py`,
как и планировалось изначально — `core/database.py` останется с одним `get_async_session()`.

## 2. Структура `api/` (новый пакет в корне)

```
api/
  __init__.py
  main.py            # FastAPI() + include_router на все роутеры ниже; ничего кроме сборки приложения
  deps.py            # SessionDep (перенесён из core/database.py) + get_current_user (JWT) + require_role(...)
  security.py        # хэш пароля (passlib/bcrypt или pwdlib), create_access_token/decode, OAuth2PasswordBearer
  routers/
    __init__.py
    auth.py          # POST /auth/register, POST /auth/login (выдаёт JWT)
    showcase.py       # GET /showcase, GET /showcase/{id}, PATCH /showcase/{id}
    users.py          # GET /users (список на approve), PATCH /users/{id}/role — только для admin/analyst
  crud/
    __init__.py
    showcase.py        # класс ShowcaseCRUD — работает с src.bp4.models.ShowcaseEvent
    users.py            # класс UserCRUD — работает с src.bp5.models.User
  schemas/
    __init__.py
    showcase.py         # ShowcaseEventRead, ShowcaseEventUpdate (pydantic)
    users.py             # UserRegister, UserLogin, UserRead, Token
```

Каждый роутер/crud импортирует модели напрямую из `src.bp4.models` / `src.bp5.models` — модели
остаются там, где живёт их бизнес-процесс, `api/` только их обслуживает. Пустые
`src/bp6/api/routers.py`/`endpoints.py` можно удалить — они были заготовкой до того, как стало
ясно, что слой общий для нескольких BP, а не локальный для bp6.

## 3. `showcase_event` API — почему нельзя просто UPDATE и как делать правильно

Витрина — **производная** таблица, это уже зафиксировано как решение в `ABOUT_PROJECT/ABOUT.md`
(BP-4, пункт 5): источник правды для `priority`/`category`/`tonality`/`action`/`deadline`/
`department`/`comment` — это `categorized_event`, а не `showcase_event`. Прямой
`UPDATE showcase_event` не упадёт, но:
- разъедется с `categorized_event` молча (аналитик увидит одно, факт-таблица хранит другое);
- если строку когда-нибудь переразметит BP-3 (`categorized_at` обновится), следующий инкремент
  BP-4 **затрёт** ручную правку без предупреждения.

**Правило для эндпоинта `PATCH /showcase/{id}`:** разрешённые к правке поля (`priority`,
`category_id`, `tonality`, `action`, `deadline`, `department_id`, `comment`) пишутся **в
`categorized_event`** (по `showcase_event.categorized_event_id`), а не в саму витрину. В той же
транзакции сразу же обновить и `showcase_event` теми же значениями (+`updated_at = datetime.now(UTC)`,
как и делает сам BP-4 — не `func.now()`, та же ловушка из ABOUT.md) — так витрина остаётся
консистентной для BI сразу, без ожидания следующего прогона BP-4. Поля, которых в
`categorized_event` нет (`title`, `media`, `region` и т.п., пришли из `normalized_item`) —
изменять через этот эндпоинт вообще нельзя, это факты, а не разметка.

`ShowcaseCRUD.update()` в `api/crud/showcase.py` — та точка, где эта логика (write-through в
`categorized_event` + зеркалирование в `showcase_event`) реализуется один раз, роутер её просто
вызывает.

## 4. Авторизация: роль ≠ отдел

Список `analytic/marketing/pr/tender/medialogick` — это **отделы** (уже есть справочник
`department`, на который ссылается `User.department_id` в `src/bp5/models.py`), а не уровни
доступа. Смешивать их в одном поле `role` — плохая идея: тендерный отдел не должен внезапно
получать права аналитика только потому, что он «отдел». Разделяем на две независимые оси:

- **`department_id`** — уже есть, справочно, «в каком отделе состоит».
- **`role`** — новый небольшой enum именно для прав доступа. Добавить в `core/enums.py`:
  ```python
  class UserRole(enum.StrEnum):
      pending = 'pending'   # только что зарегистрировался, доступа нет
      viewer = 'viewer'     # читает витрину/свои задачи, править не может
      analyst = 'analyst'   # правит витрину, подтверждает pending → viewer/analyst
      admin = 'admin'       # + управление пользователями/справочниками
  user_role = Enum(UserRole, name='user_role')
  ```

**Регистрация:** self-service signup + approval — `role=pending` по умолчанию
(`server_default=text("'pending'")`, как у других enum-полей в проекте). `pending` физически не
даёт доступа ни к одному эндпоинту кроме `GET /users/me`. `ActiveMixin.is_active` не трогаем — у
него другой смысл (уволен/в отпуске).

**В `src/bp5/models.py::User` добавить:**
```python
password_hash: Mapped[str] = mapped_column(StrippedString(256), comment='bcrypt-хэш пароля')
role: Mapped[UserRole] = mapped_column(user_role, default=UserRole.pending, server_default=text("'pending'"))
```

**Важный побочный эффект переиспользования `bp5.User`:** сейчас `email` и `telegram_id` — оба
`NOT NULL UNIQUE`. Если разрешаем самостоятельную регистрацию по email+паролю, `telegram_id` в
момент регистрации ещё не известен — его нужно сделать `Mapped[int | None]`. Тогда пользователь
может залогиниться и работать в системе, но не получать telegram-алерты, пока сам не привяжет
`telegram_id` — ожидаемое ограничение. Потребуется миграция Alembic на nullable + новые колонки.

**JWT:** `api/security.py` — хэш пароля (`bcrypt` через `passlib` или `pwdlib`, добавить в
`requirements.txt`), `create_access_token`/`decode_access_token` (`python-jose` или `PyJWT`,
секрет — новое поле в `core/config.py`: `jwt_secret_key: str`, `jwt_expire_minutes: int = 60`).
`api/deps.py::get_current_user` — декодирует токен, читает `User` по `sub`, отдаёт как
`Annotated[User, Depends(...)]`. `require_role('analyst', 'admin')` — фабрика зависимостей для
проверки роли на конкретном роутере (просто `if user.role not in allowed: raise HTTPException(403)`
— без отдельной библиотеки прав, ролей всего 4, усложнять не нужно).

## 5. Где живёт запуск пайплайнов, пока работает FastAPI

Пайплайны сейчас — обычные `async def run_bp2()/run_bp4()/run_bp5()` (`src/bp2/pipeline.py:285`,
`src/bp4/pipeline.py:120`, `src/bp5/pipeline.py:265`), вызываются напрямую. Единственная
Celery-задача во всём проекте — `run_parser_task` в BP-1, но самого `Celery()` app нигде нет (см.
отдельный разбор BP-1/Celery/Redis/логирования от 2026-08-02).

**FastAPI и обработка пайплайнов — не один процесс, а два независимых.** `api/main.py` — только
HTTP-сервер (`uvicorn api.main:app`), он не должен сам гонять долгие пайплайны (парсинг/LLM могут
идти минутами — блокировать event loop веб-сервера нельзя). Оркестрация пайплайнов остаётся
задачей Celery+Beat, отдельным процессом (`celery -A core.celery_app worker -B`). Один Celery app
на весь проект (тот же, что нужен для BP-1) — в него добавляются задачи-обёртки `run_bp2_task`,
`run_bp4_task`, `run_bp5_task` (`@shared_task`, тонкие обёртки над уже существующими `run_bp2()` и
т.д.), плюс `beat_schedule` на периодичность.

Так `api/main.py` остаётся простым: только `FastAPI()` + `include_router(...)`, никакой
пайплайн-логики в нём нет.

---

## Порядок реализации

1. `core/enums.py` — добавить `UserRole`.
2. `src/bp5/models.py` — `password_hash`, `role`; `telegram_id` → nullable. Alembic-миграция.
3. `core/database.py` — убрать `SessionDep`/`Depends`/`fastapi`-импорт.
4. `api/` — `deps.py` (с перенесённым `SessionDep` + `get_current_user`/`require_role`),
   `security.py`, `schemas/`, `crud/`, `routers/auth.py`, `routers/users.py`, `routers/showcase.py`,
   `main.py`. Удалить пустые `src/bp6/api/*.py`.
5. `core/config.py` — добавить `jwt_secret_key`, `jwt_expire_minutes`.
6. `requirements.txt` — добавить JWT/хэш-библиотеки.

## Проверка

- `python -m api.main` стартует без ошибок импорта на порту из `API_PORT`.
- `POST /auth/register` → в БД строка `role=pending`; `GET /users/me` под её токеном не даёт
  доступа к `showcase`; `admin`/`analyst` меняет роль → доступ появляется.
- `PATCH /showcase/{id}` с новым `priority` → проверить, что `categorized_event.priority` тоже
  обновился (не только витрина) — ручным `SELECT` после вызова.
- Прогнать `run_bp4()` после ручной правки — витрина не должна «откатиться» к старому значению,
  пока `categorized_event` не переразметят заново.

---

## 6. Справочники + просмотр данных пайплайна (BP-1…BP-5) — РЕАЛИЗОВАНО

Обсуждено 2026-08-04, сделано позже — **обе части, и они не заменяют друг друга**:

- **JSON-эндпоинты** (план ниже) — реализованы: generic-слой `api/crud/reference.py`,
  `api/service/reference.py`, `api/endpoints/reference.py` + по файлу схем/роутера на таблицу.
  Нужны кастомному фронту и интеграциям.
- **HTML-админка** — реализована на **FastAdmin** (не SQLAdmin, как предполагалось изначально;
  документация в `ABOUT.md` приведена в соответствие). Код — `api/admin/`, инструкция по
  запуску — `api/ADMIN_README.md`. Монтируется в тот же процесс на `/admin`.

Текст ниже оставлен как описание принятой архитектуры JSON-слоя.

### Группа «Администрирование» — generic CRUD над 12 справочниками

Таблицы: `competitor`, `source`, `trigger`, `region`, `black_domain`, `stop_word`, `topic_limit`,
`category`, `department`, `event_type`, `channel`, `routing_rule`. Доступ — `EditorDep`
(analyst/admin).

На каждую: `GET ''` (список + поиск/фильтры), `GET '/{id}'`, `POST ''`, `PATCH '/{id}'`,
`DELETE '/{id}'` — **мягкое** удаление (`is_active=False`, физически строка не удаляется). `GET`
по умолчанию отдаёт все строки, включая `is_active=False` (аналитику нужно видеть выключенные,
чтобы включить обратно), с опциональным query-фильтром `is_active`. «Восстановление» —
`PATCH {id}` с `is_active=true`, отдельный endpoint не нужен.

**Проверить перед реализацией:** `region` (`src/bp2/models.py`) сейчас **без** `ActiveMixin` (нет
`is_active`), как `raw_item`/`normalized_item`. Чтобы включить её в эту группу с мягким
удалением — сначала модельная правка + Alembic-миграция (добавить `ActiveMixin`).

**Архитектура — один generic CRUD-слой, не 12 отдельных реализаций:**
- `api/crud/reference.py` — `ReferenceCRUD` (`__init__(session, model)`); методы `get(id)`,
  `list_all(filters: dict, search: dict[str, str])` (`filters` — точное совпадение, `search` —
  `ilike` по указанным строковым полям), `create(data: dict)`, `update(item, changes: dict)`,
  `soft_delete(item)` (`is_active=False`, `flush`). Работает с любой моделью с `Mixin`+`ActiveMixin`.
- `api/service/reference.py` — `ReferenceService`, добавляет проверку уникальности (409 при
  конфликте на `unique=True` полях/составных `UniqueConstraint`, включая `routing_rule`) поверх
  generic CRUD.
- `api/endpoints/reference.py` — фабрика `build_reference_router(model, read_schema,
  create_schema, update_schema, *, search_fields, tag)`, собирающая `APIRouter` с пятью
  стандартными путями.
- Под каждую из 12 таблиц — маленький файл (~10-15 строк): только Pydantic Read/Create/Update-
  схемы (поля у всех разные — `competitor` это `name`+`inn`, `event_type` — `name`+
  `keywords: list[str]`, `routing_rule` — 4 FK + 2 enum и т.д.) и один вызов фабрики с нужными
  `search_fields`.

### Группа «Данные после парсинга» (BP-1)

- `search_task` — тот же generic CRUD + поиск (по `competitor_id`/`source_id`/`trigger_id`),
  доступ `EditorDep`. Нужен для удобного добавления новых комбинаций конкурент+источник+триггер
  без похода в БД руками.
- `raw_item` — **только просмотр**: `GET ''` (фильтры: `status`, `search_task_id`, диапазон
  `created_at`/`updated_at`) + `GET '/{id}'`. Без CRUD — «грязная» таблица сырья, смотреть, не
  редактировать.

### Группа «Данные после нормализации» (BP-2)

- `normalized_item` — только просмотр: `GET ''` (фильтры: `status`, `reject_reason`,
  `competitor_id`, `region_id`, диапазон `published_at`, поиск по `title`) + `GET '/{id}'`.
  Причина не делать правку: у модели нет `updated_at` — даже при появлении настоящего
  инкрементального BP-3 (по образцу BP-4/BP-5) правка постфактум никогда не будет замечена
  повторным прогоном.

### Группа «Данные после проработки LLM» (BP-3)

- `categorized_event` — только просмотр: `GET ''` (фильтры: `priority`, `category_id`,
  `department_id`, диапазон `categorized_at`) + `GET '/{id}'`. Единственный путь правки этих
  данных — уже существующий `PATCH /showcase/{id}` (см. раздел 3 выше): он одновременно пишет в
  `categorized_event` и зеркалит в `showcase_event`; отдельный прямой `PATCH` сломал бы это
  зеркалирование.

### Группа «Отправленные уведомления» (BP-5)

- `alert` — только просмотр: `GET ''` (фильтры: `status`, `channel_id`, `user_id`, `priority`,
  `mode`, диапазон `created_at`/`sent_at`) + `GET '/{id}'`. Неизменяемый журнал доставки (пишет
  `sync_alerts`, `ActiveMixin` нет) — правка status/error_message задним числом испортила бы
  историю.

Везде доступ — `EditorDep` (analyst/admin): внутренняя механика пайплайна, не для роли
`viewer`/отделов.

Swagger-теги: «Администрирование», «Данные после парсинга (BP-1)», «Данные после нормализации
(BP-2)», «Данные после проработки LLM (BP-3)», «Отправленные уведомления (BP-5)».
