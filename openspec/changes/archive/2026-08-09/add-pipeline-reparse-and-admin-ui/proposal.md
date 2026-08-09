## Why

Раннер этапов (`add-pipeline-stage-runner`) закрыл только «прогнать заново с нуля». На практике выяснилось: когда справочник фильтров (стоп-слова, чёрные домены) меняют ПОСЛЕ того, как строка уже нормализована, обычный прогон этап 2 её не пересматривает — `select_pending_raw_items()` берёт только необработанные снимки. У `run_bp2()` для этого уже есть параметр `reparse`, но раннер (`core/pipeline/registry.py`) его не подключает вообще — добраться до пересборки можно только в обход раннера, напрямую через `python -m src.bp2.pipeline reparse`, то есть ровно то место, куда раннер должен был убрать прямые обращения к скриптам. Заодно раннер сейчас доступен только из терминала — нужно вывести его же в уже существующую админку (FastAdmin), чтобы отдельным терминалом для каждого прогона не пользоваться.

## What Changes

- `core/pipeline/registry.py` — `StageDescriptor` получает необязательную вторую точку входа `run_reparse: Callable[[], Awaitable[dict]] | None` (по умолчанию `None`). У этапа 2 (BP-2) она заполнена — вызывает `run_bp2(reparse=True)`. У остальных этапов — `None`: пересборки как концепции для них сегодня не существует, придумывать её не будем.
- `core/pipeline/runner.py::run_stage()` — новый параметр `reparse: bool = False`. При `reparse=True` вызывается `descriptor.run_reparse`, если он есть; если у этапа нет режима пересборки, а `reparse=True` запрошен — понятная ошибка, а не тихий обычный прогон.
- `core/pipeline/cli.py` — минимальное расширение: `python -m core.pipeline.cli 2 reparse` (доп. позиционный аргумент), без новых флагов сверх необходимого.
- Новая модель-маркер `core/pipeline/models.py::PipelineControlMarker` — пустая таблица без данных, единственная цель — быть host-моделью для кнопок в FastAdmin (`@register` требует настоящую SQLAlchemy-модель). Новая Alembic-ревизия.
- Новый `api/admin/pipeline_control.py` — регистрирует `PipelineControlMarker`, с `@widget_action`-кнопками: по одной на каждый из 7 этапов (запускает `core.pipeline.runner.run_stage(N)`) + кнопка «Запустить всё» (`run_all()`). Под кнопкой этапа 2 — чекбокс «пересобрать» (`widget_action_filters` с `WidgetType.Checkbox`), включает `reparse=True` именно для этого вызова.
- `api/admin/base.py` — новая константа раздела меню `MENU_PIPELINE_CONTROL = 'Пайплайн'`, отдельно от уже существующей `MENU_PIPELINE = 'Данные конвейера'` (тот раздел — read-only просмотр таблиц конвейера, другая сущность, тот же корень слова не должен путать).
- `api/admin/__init__.py` — `pipeline_control` импортируется первым в списке (гипотеза: порядок импорта = порядок раздела в сайдбаре FastAdmin; проверяется вживую на реализации, см. design.md).

## Non-goals (сознательно вне этого изменения)

- API-эндпоинты (`FastAPI /pipeline/...`) — отдельная будущая задача, следующий шаг после этой.
- Reparse для этапов, кроме BP-2 — такой концепции для остальных `src/bpN/pipeline.py` сегодня нет.
- Права доступа тоньше существующей модели ролей (`admin`/`analyst`) — кнопки доступны так же, как остальная запись в админке сегодня, отдельное разграничение не вводим.

## Capabilities

### New Capabilities
- `admin/pipeline-control`: кнопки запуска этапов конвейера (по номеру, все подряд, с пересборкой для этапа 2) прямо в существующей FastAdmin-панели.

### Modified Capabilities
- `core/pipeline-stage-runner`: требование «Запуск одного этапа по номеру» расширяется — этап может поддерживать альтернативный режим запуска (пересборка), задача его запросить понятно отклоняется, если этап такой режим не поддерживает.

## Impact

- **Новое:** `core/pipeline/models.py`, Alembic-ревизия под неё, `api/admin/pipeline_control.py`.
- **Правится:** `core/pipeline/registry.py`, `core/pipeline/runner.py`, `core/pipeline/cli.py`, `api/admin/base.py`, `api/admin/__init__.py`.
- **Не меняется:** `run_bp2`/`run_bp4`/`run_bp5`/`run_bp7_promotion`, заглушки `core/scripts/stages/*`, `src/bp3/pipeline.py`.
- Порядок архивации: этот change логически продолжает `add-pipeline-stage-runner` (delta правится поверх его требования). Пока тот не заархивирован, основной спеки `openspec/specs/core/pipeline-stage-runner/` ещё нет на диске — merge этой delta корректно сработает только после (или вместе с) архивации `add-pipeline-stage-runner`.
