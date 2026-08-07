## 1. Reparse в реестре и раннере

- [ ] 1.1 `core/pipeline/registry.py` — добавить поле `run_reparse: Callable[[], Awaitable[dict]] | None` в `StageDescriptor` (по умолчанию `None`)
- [ ] 1.2 У этапа 2 (BP-2) заполнить `run_reparse` — обёртка над `run_bp2(reparse=True)`
- [ ] 1.3 `core/pipeline/runner.py::run_stage()` — новый параметр `reparse: bool = False`; при `True` вызывает `descriptor.run_reparse`, если он задан
- [ ] 1.4 Если `reparse=True` запрошен, а `descriptor.run_reparse is None` — понятная ошибка («этот этап не поддерживает пересборку»), без тихого отката на обычный запуск
- [ ] 1.5 `core/pipeline/cli.py` — принять доп. позиционный аргумент `reparse` (`python -m core.pipeline.cli 2 reparse`)

## 2. Модель-маркер и миграция

- [ ] 2.1 `core/pipeline/models.py::PipelineControlMarker` — пустая модель (только `id`), без бизнес-полей
- [ ] 2.2 Alembic-ревизия: создать таблицу маркера
- [ ] 2.3 Применить миграцию (`alembic upgrade head`), убедиться, что таблица создалась пустой

## 3. Регистрация в FastAdmin

- [ ] 3.1 `api/admin/base.py` — добавить `MENU_PIPELINE_CONTROL = 'Пайплайн'`
- [ ] 3.2 Новый `api/admin/pipeline_control.py` — `@register(PipelineControlMarker, ...)`, класс на основе `ReadOnlyModelAdmin` (добавление/правка/удаление строк не нужны)
- [ ] 3.3 По одному `@widget_action`-методу на каждый из 7 этапов — вызывает `core.pipeline.runner.run_stage(N)`, возвращает результат в `WidgetActionResponseSchema`
- [ ] 3.4 `@widget_action`-метод «Запустить всё» — вызывает `core.pipeline.runner.run_all()`, форматирует сводку по всем этапам в ответ
- [ ] 3.5 У кнопки этапа 2 — `widget_action_filters` с полем `WidgetType.Checkbox` («пересобрать»); значение из `payload` явно приводится к `bool` перед передачей в `run_stage(2, reparse=...)`
- [ ] 3.6 `api/admin/__init__.py` — импортировать `pipeline_control` первым в списке модулей админки

## 4. Проверка вживую

- [ ] 4.1 Открыть `/admin`, зайти в раздел «Пайплайн», убедиться что кнопки на месте (независимо от фактической позиции раздела в сайдбаре — см. design.md, Open Questions)
- [ ] 4.2 Нажать кнопку этапа 2 без чекбокса — обычный прогон, поведение как у CLI
- [ ] 4.3 Отредактировать активное стоп-слово так, чтобы оно совпадало с уже нормализованной строкой; нажать кнопку этапа 2 С чекбоксом «пересобрать» — убедиться, что строка пересчиталась (`reject_reason` заполнился) без повторного сбора
- [ ] 4.4 Нажать кнопку этапа с несуществующими предусловиями (например, этап 4 на пустых данных) — убедиться, что ошибка preflight отображается в админке так же понятно, как в CLI
- [ ] 4.5 Нажать «Запустить всё» — сверить сводку в админке с тем, что даёт `python -m core.pipeline.cli all`
- [ ] 4.6 `ruff check` по новым/изменённым файлам
