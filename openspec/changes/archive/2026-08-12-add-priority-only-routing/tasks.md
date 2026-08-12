## 1. Модель и миграция

- [x] 1.1 `src/bp5/models.py::RoutingRule` — тип события становится необязательным (`Mapped[int | None]`), обновить комментарий колонки: пусто = «любой тип события»
- [x] 1.2 `RoutingRule.__table_args__` — существующий `UniqueConstraint` (тип+приоритет+канал+получатель) не трогаем (NULL != NULL уже не даёт ему видеть дубли без типа), добавлен частичный уникальный индекс `uq_routing_rule_no_type_priority_channel_user` для случая «тип не задан» (по образцу `uq_search_task_no_trigger` в `src/bp1/models.py`)
- [x] 1.3 `src/bp5/models.py::Alert` — тип события становится необязательным, обновить комментарий колонки: пусто = сработало правило по приоритету, тип не распознан
- [x] 1.4 Обновить докстринг модуля `src/bp5/models.py` — описание маршрутизации упоминает оба вида правил
- [x] 1.5 Ревизия `44cc7e12d384`; из автогенерации вычищен несвязанный дрейф `source_candidate.domain` NOT NULL (тот же известный, ранее отмеченный дрейф, что и в `d5a9a93f4f4a`) — в миграцию не включён
- [x] 1.6 Применена (`alembic upgrade head`). Проверено `information_schema`/`pg_indexes`: оба поля nullable, новый частичный индекс на месте, старый constraint не тронут. Существующих строк в `routing_rule`/`alert` на этой БД не было (0/0) — терять было нечего

## 2. Загрузка и группировка правил

- [x] 2.1 `src/bp5/crud.py::load_routing_rules` — двухуровневая группировка: правила с типом по ключу «(тип, приоритет)» в `RoutingRuleGroups.by_type`, правила без типа по ключу «приоритет» в `.by_priority`
- [x] 2.2 Докстринг метода и `RoutingRuleGroups` обновлены — что возвращается и почему два словаря вместо одного
- [x] 2.3 Один `select` на весь `load_routing_rules()`, как и раньше — группировка происходит в памяти после единственного запроса, per-event обращений к БД как не было, так и нет

## 3. Логика детектора

- [x] 3.1 `src/bp5/pipeline.py::sync_alerts` — ранний `continue` при нераспознанном типе убран; событие без типа доходит до проверки правил по приоритету
- [x] 3.2 `typed_rules`/`priority_rules` — два прохода по `RoutingRuleGroups.by_type`/`.by_priority`
- [x] 3.3 Новая чистая функция `merge_rule_overlap()` — при совпадении (user_id, channel_id) оставляет типовое правило, приоритетное отбрасывает
- [x] 3.4 `build_alert_rows` — `matched_type_id: int | None` пишется в каждую строку как есть (см. докстринг функции); отдельной ветки по правилу не нужно — тип события и то, какое правило сработало, независимы
- [x] 3.5 `matched` оставлен с тем же смыслом — «тип распознан» (см. докстринг модуля); задокументировано явно, что это НЕ то же самое, что «алерт создан», и что теперь возможны обе комбинации matched/alerts независимо
- [x] 3.6 Докстринг модуля обновлён — порядок шагов, порог значимости, оба вида правил, смысл `matched`

## 4. API и админка

- [x] 4.1 `api/schemas/routing_rule.py` — `event_type_id: int | None` в Read/Create; Update уже был `int | None = None` (partial-update семантика через `exclude_unset=True` в `api/endpoints/reference.py` уже различает «поле не передано» от «явный null» — довокументировано комментарием)
- [x] 4.2 `RoutingRuleAdmin.formfield_overrides['event_type']` — `WidgetType.AsyncSelect` с `placeholder`, явно говорящим «не выбирайте — любой тип». `RoutingRuleInline` (на странице типа события) НЕ трогаем — там поле типа скрыто FastAdmin как связь с родителем, правило без типа с этой страницы принципиально не завести, только через список ниже
- [x] 4.3 Пустая ячейка `event_type` в списке уже рендерится как `—` (`RelatedLabelMixin.EMPTY`, общий механизм проекта для всех nullable FK) — не «пустая», а осмысленный прочерк; задокументировано в докстринге `RoutingRuleAdmin` и в BP5_README (см. 5.1)

## 5. Документация и справочники

- [x] 5.1 `src/bp5/BP5_README.md` — раздел `routing_rule` переписан: оба вида правил, наложение, предупреждение про ширину охвата правила по приоритету
- [x] 5.2 Решено: НЕ добавлять пример правила без типа в `dictionaries.py`/`simple_dictionaries.py` (см. design.md, Risks — правило по приоритету создаёт заметно больше алертов, чем ожидает заполняющий демо-данные) — код сидеров не менялся

## 6. Проверка

- [x] 6.1 Покрыто существующим `test_matched_event_creates_alert` (не менялся, всё ещё зелёный) — алерт создаётся как раньше, тип в журнале заполнен
- [x] 6.2 Новый `test_priority_only_rule_matches_unrecognized_title` — алерт создаётся, `matched=0`, `alert.event_type_id is None`
- [x] 6.3 Новый `test_no_match_marks_checked_and_not_repicked` — алерта нет, событие не возвращается в `select_pending_events` повторно
- [x] 6.4 Новый `test_typed_and_priority_rule_overlap_single_delivery` — ровно одна доставка, `alert.event_type_id == event_type.id`
- [x] 6.5 Новый `test_typed_and_priority_rule_different_recipients_both_alert` — 2 алерта, оба получателя
- [x] 6.6 Новый `test_duplicate_priority_only_rule_rejected` — второй `flush()` падает `IntegrityError` на частичном индексе
- [x] 6.7 Покрыто существующим `test_sync_alerts_is_idempotent` (не менялся, зелёный)
- [x] 6.8 `ruff check` — чисто (алембик-warnings в миграции — ложные, `alembic/` целиком исключена в `pyproject.toml`, как и у всех остальных миграций проекта). Полный `pytest`: 462 passed; 31 ошибка в `tests/bp1/fedresurs/*` — baseline, не хватает fixture `mocker` (pytest-mock не установлен), не связано с этим change и не regressed им. Новые/изменённые тесты BP-5: 59 passed (было 51 до этого change: +2 юнит-теста build_alert_rows/merge_rule_overlap ×5, +1 тест load_routing_rules, +5 интеграционных сценариев 6.2–6.6)
