## Context

См. proposal.md - Why. Технические факты, найденные при разборе:

- `run_bp2(reparse: bool = False, raw_item_ids: Sequence[int] | None = None)` уже умеет пересобирать (`src/bp2/pipeline.py:285`) — параметра не хватает только в реестре (`core/pipeline/registry.py`), который сегодня жёстко зовёт `run_bp2` без аргументов.
- FastAdmin (`venv/Lib/site-packages/fastadmin`) поддерживает `@widget_action` (`fastadmin/models/decorators.py:64`) — метод на `ModelAdmin`, декорированный `widget_action_type=WidgetActionType.Action`, рендерится как кнопка на странице модели; `widget_action_filters` (список `WidgetActionFilter(field_name, widget_type, widget_props)`) добавляет туда же интерактивные поля — `WidgetType.Checkbox` в их числе. Обработчик получает `payload: WidgetActionInputSchema` с текущими значениями фильтров (`fastadmin/api/service.py:568`) и обязан вернуть `WidgetActionResponseSchema`.
- `@register(model, **kwargs)` требует минимум одну настоящую SQLAlchemy-модель (`fastadmin/models/decorators.py:201`: `"At least one model must be passed to register"`) — `widget_actions` не существуют сами по себе, они всегда прибиты к какой-то зарегистрированной модели и рендерятся на ЕЁ странице (`widget_actions` — поле `BaseModelSchema`, `fastadmin/models/schemas.py:202`), не на едином сайтовом дашборде.
- В `api/admin/pipeline.py` уже существует раздел `MENU_PIPELINE = 'Данные конвейера'` (`api/admin/base.py:100`) — read-only просмотр таблиц слоёв конвейера. Это другая сущность, не «запуск этапов»; переиспользовать то же имя раздела или сам файл `pipeline.py` нельзя — будет путаница.
- Alembic в проекте — инкрементальные ревизии (`alembic/versions/*`, 6 штук на момент написания), не единая init-миграция — новая таблица оформляется обычной новой ревизией.
- `add-pipeline-stage-runner` (капабилити `core/pipeline-stage-runner`) реализован, но ещё не заархивирован — `openspec/specs/core/pipeline-stage-runner/` на диске не существует. Delta «MODIFIED» в этом change пишется по содержимому его ещё-не-заархивированной delta-спеки (уже реализовано и верно сегодня, просто ждёт архивации).

## Goals / Non-Goals

**Goals:**
- Пересборка этапа 2 доступна через тот же `run_stage()`, что и обычный запуск — не отдельный путь мимо реестра.
- Кнопки в админке дёргают ровно `core.pipeline.runner` — не дублируют и не обходят его логику (preflight, сводка, пометка заглушек).
- Новая модель-маркер ничего не хранит и не имеет отношения к бизнес-данным — только технический якорь для `@register`.

**Non-Goals:**
- Общий механизм «пересборки» для всех этапов — есть только там, где уже есть `reparse` в реальном коде (этап 2).
- API-эндпоинты и права доступа тоньше существующей модели ролей — см. proposal.md, Non-goals.

## Decisions

### `StageDescriptor.run_reparse` — вторая, необязательная точка входа, а не общий `**kwargs`
Вариант «раз реестр уже дёргает `Callable[[], Awaitable[dict]]`, можно просто расширить сигнатуру до `Callable[..., Awaitable[dict]]` и прокидывать произвольные опции» — отклонён: тогда каждый вызывающий код должен знать, какие опции понимает конкретный этап, а `run_stage()` не сможет провалидировать «этот этап не поддерживает такую опцию» без специального списка допустимых имён на каждый этап. Отдельное поле `run_reparse: Callable[[], Awaitable[dict]] | None` — `None` у шести этапов из семи, заполнено только у этапа 2 — даёт `run_stage()` тривиальную проверку (`if reparse and descriptor.run_reparse is None: raise`) без домысливания опций.

### Модель-маркер живёт в `core/pipeline/models.py`, не в `src/bpN/`
Выбор пользователя (см. вопрос в ходе planning) — новая пустая модель, а не привязка к существующей `src/bp1/models.py::RawItem` и т.п. Файл кладём в `core/pipeline/` (не в `api/admin/`), потому что модель — часть пакета раннера по смыслу (это его «якорь» в БД), а `api/admin/` по конвенции проекта только РЕГИСТРИРУЕТ уже существующие модели, не объявляет свои (см. `api/admin/pipeline.py`, `workflow.py`, `parsing.py` — везде импорт `Model` из `src/bpN/models.py`).

### Новый раздел меню `MENU_PIPELINE_CONTROL = 'Пайплайн'`, новый файл `api/admin/pipeline_control.py`
Не переиспользуем `MENU_PIPELINE`/`api/admin/pipeline.py` — та страница про ДАННЫЕ конвейера (read-only таблицы), эта — про ЗАПУСК этапов. Общий корень слова уже мог бы путать, общее имя файла/константы — тем более.

### Порядок раздела в сайдбаре — открытый технический вопрос, не блокирующий план
Гипотеза («порядок импорта = порядок в сайдбаре, значит `pipeline_control` — первым в списке импортов») не пережила реализацию буквально: `ruff` (isort-правило I001) настойчиво пересортировывает `from api.admin import (...)` по алфавиту при любой попытке вынести `pipeline_control` первым (включая отдельную инструкцию импорта — ruff всё равно сливает её с соседней из того же модуля). Биться с линтером ради непроверенного механизма позиционирования признано нецелесообразным — импорт оставлен в алфавитном порядке (`alerting, normalization, parsing, pipeline, pipeline_control, users, workflow`), а фактическая позиция раздела «Пайплайн» в сайдбаре проверяется по факту на шаге 4.1 tasks.md. Как и было зафиксировано изначально — это не меняет ни спеку, ни поведение системы, только видимое место пункта меню.

### Разрешения на кнопки — без нового механизма
`@widget_action`-методы, как и обычные `@action`, проверяются через стандартные permission-хуки `BaseModelAdmin` (`has_change_permission` и т.п.) — используем тот же паттерн, что и `KodikModelAdmin` уже применяет к обычным моделям (доступно `admin`/`analyst`, как и остальная админка), никакого отдельного разрешения не вводим.

## Risks / Trade-offs

- [Risk] `PipelineControlMarker` — пустая таблица без данных, непривычная для admin-панели (обычно там CRUD над реальными записями) → Mitigation: `has_add_permission`/`has_change_permission`/`has_delete_permission` отключены (как у `ReadOnlyModelAdmin`) — открыть можно только страницу с кнопками, ни одной строки в списке никогда не будет.
- [Risk] `@widget_action`-метод получает `payload: WidgetActionInputSchema` (одна структура на все фильтры) — если формат поля чекбокса окажется не тем, что ожидается (например, строка `"true"` вместо `bool`), пересборка может включиться неверно → Mitigation: явная проверка типа значения перед передачей в `run_stage(reparse=...)`, вместо доверия сырому payload.
- [Risk] Долгий этап (например, этап 3 — реальный LLM/Tavily вызов, видели прогон ~6 минут) блокирует HTTP-запрос кнопки на всё это время → Mitigation: не в скоупе этого изменения (Celery — Non-goal и здесь, и в `add-pipeline-stage-runner`); фиксируется как известное ограничение, не решается сейчас.

## Migration Plan

Новая таблица без данных — миграция только создаёт её, откат — обычный `downgrade` (`DROP TABLE`), без риска для существующих данных. Порядок реализации:
1. `core/pipeline/models.py::PipelineControlMarker` + Alembic-ревизия.
2. `core/pipeline/registry.py` — `run_reparse` у этапа 2.
3. `core/pipeline/runner.py::run_stage(number, *, reparse=False)`.
4. `core/pipeline/cli.py` — позиционный `reparse`.
5. `api/admin/base.py` — `MENU_PIPELINE_CONTROL`.
6. `api/admin/pipeline_control.py` — регистрация + 7 кнопок этапов + кнопка «Запустить всё» + чекбокс у этапа 2.
7. `api/admin/__init__.py` — импорт `pipeline_control` первым.
8. Ручная проверка: каждая кнопка в браузере, чекбокс пересборки, `run_all()`-кнопка.

Откат — ревёрт коммита + `alembic downgrade -1` для новой ревизии.

## Open Questions

- Реальный порядок раздела «Пайплайн» в сайдбаре FastAdmin (по импорту, по алфавиту, или как-то ещё) — не влияет на спеку/поведение, проверяется по факту при реализации.
