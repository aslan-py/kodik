## 1. Модель

- [x] 1.1 В `src/bp3/models.py` добавить в `CategorizedEvent` поле `expected_result: Mapped[str | None] = mapped_column(Text, comment=...)` — импорт `Text` из `sqlalchemy` (уже используется как паттерн в `src/bp6/models.py::ActionItem.expected_result`), комментарий в духе «Ожидаемый результат по событию. Источника в BP-3 пока нет — заполняется NULL, задел под будущий LLM-модуль».

## 2. Миграция

- [x] 2.1 Сгенерировать Alembic-ревизию (`alembic revision --autogenerate -m "add categorized_event.expected_result"`) поверх текущей головной ревизии.
- [x] 2.2 Проверить сгенерированный `upgrade`/`downgrade` — только `add_column`/`drop_column` на `categorized_event.expected_result`, без лишних диффов от несвязанных моделей.
- [x] 2.3 Прогнать миграцию на локальной БД (`alembic upgrade head`), убедиться что откат (`alembic downgrade -1`) тоже проходит.

## 3. Смежные слои чтения

- [x] 3.1 Добавить `expected_result: str | None` в `CategorizedEventRead` (`api/schemas/categorized_event.py`).
- [x] 3.2 Добавить `expected_result` в `list_display`/`list_display_labels` `CategorizedEventAdmin` (`api/admin/pipeline.py`) — по аналогии с `action`/`comment`.

## 4. Проверка

- [x] 4.1 Убедиться, что существующее сохранение `CategorizedEvent` (`SaveResultsModule`) продолжает работать без изменений — `expected_result` не передаётся в конструктор и остаётся `NULL`, ошибок нет. Проверено импортом модуля и прямым запросом к БД: строки normalized_item_id 229/230 читаются, `expected_result IS NULL`.
- [x] 4.2 Убедиться, что `alembic upgrade head` и запуск приложения/админки не ломаются на новом nullable-поле. Проверено: модель загружается (`CategorizedEvent.__table__.columns` содержит `expected_result`), `api.admin.pipeline` импортируется без ошибок, `list_display` содержит новое поле.
