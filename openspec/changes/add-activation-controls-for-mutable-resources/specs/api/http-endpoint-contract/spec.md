## MODIFIED Requirements

### Requirement: Каждая операция возвращает ответ заявленной схемы
Для корректного запроса каждая операция SHALL возвращать документированный HTTP-код и тело, соответствующее своей OpenAPI-схеме. Это требование SHALL охватывать авторизацию, пользователей, витрину, план действий, задачи поиска, справочники и read-only данные этапов конвейера. `PATCH` для каждого ресурса, имеющего soft `DELETE`, SHALL принимать `is_active` как опциональное изменяемое поле наряду с остальными полями ресурса; к таким ресурсам относятся competitor, source, trigger, search_task, black_domain, stop_word, topic_limit, category, department, event_type, channel и routing_rule. `DELETE` SHALL сохранять существующую семантику установки `is_active=false`.

#### Scenario: Успешное чтение списка и объекта
- **WHEN** разрешённый клиент запрашивает список с поддерживаемыми фильтрами или существующий объект по идентификатору
- **THEN** сервер возвращает `200`, тело заявленной схемы и данные, соответствующие фильтрам и области видимости пользователя

#### Scenario: Успешное создание
- **WHEN** разрешённый клиент отправляет корректное тело в операцию создания
- **THEN** сервер возвращает документированный код создания и созданный объект заявленной схемы

#### Scenario: Успешное частичное обновление
- **WHEN** разрешённый клиент отправляет допустимый непустой набор изменяемых полей существующего объекта
- **THEN** сервер возвращает `200`, изменяет только переданные поля и возвращает обновлённый объект заявленной схемы

#### Scenario: Деактивация и реактивация через PATCH
- **WHEN** analyst или admin отправляет `PATCH` существующего soft-deletable ресурса с `is_active=false`, а затем с `is_active=true`
- **THEN** каждый запрос возвращает `200`, сохраняет строку и устанавливает запрошенное состояние без изменения непереданных полей

#### Scenario: Мягкое удаление справочника
- **WHEN** разрешённый клиент удаляет существующий элемент справочника, поддерживающего удаление
- **THEN** сервер возвращает `200`, оставляет строку в хранилище и переводит её в неактивное состояние

### Requirement: Варианты фильтров включают СМИ и диапазон дедлайнов
`GET /filter-options` SHALL включать в секцию `showcase` поле `media`: отсортированный без учёта регистра массив уникальных непустых значений `showcase_event.media`. `GET /showcase` SHALL принимать необязательный параметр `media` и возвращать события, чьё значение СМИ совпадает с ним по регистронезависимому поиску подстроки.

Вместо массива индивидуальных дат `action_items.deadline` SHALL быть объектом `{from, to}`. `from` и `to` SHALL быть соответственно минимальным и максимальным ненулевым дедлайном доступных пользователю задач в ISO-формате `YYYY-MM-DD`; если таких дат нет, оба поля SHALL быть `null`. Роль `viewer` SHALL вычислять границы только по задачам своего отдела.

`GET /action-items` SHALL принимать необязательные включительные параметры `deadline_from` и `deadline_to` вместо точного параметра `deadline`. При передаче обеих границ `deadline_from` не SHALL быть больше `deadline_to`; иначе API SHALL вернуть `422`.

#### Scenario: Справочник возвращает применимое СМИ
- **WHEN** витрина содержит несколько событий с повторяющимся непустым `media`
- **THEN** `GET /filter-options` возвращает каждое СМИ один раз в `showcase.media`, а `GET /showcase?media=<значение>` возвращает соответствующие события

#### Scenario: Справочник возвращает границы дедлайнов
- **WHEN** доступные пользователю задачи имеют ненулевые дедлайны `2026-08-14` и `2026-08-15`
- **THEN** `action_items.deadline` равно `{ "from": "2026-08-14", "to": "2026-08-15" }`

#### Scenario: Варианты дедлайнов отсутствуют
- **WHEN** среди доступных пользователю задач нет ненулевых дедлайнов
- **THEN** `action_items.deadline` равно `{ "from": null, "to": null }`

#### Scenario: Фильтрация задач по диапазону дедлайнов
- **WHEN** разрешённый пользователь передаёт `deadline_from=2026-08-14` и `deadline_to=2026-08-15` в `GET /action-items`
- **THEN** сервер возвращает только видимые задачи со сроком в этом включительном диапазоне

## ADDED Requirements

### Requirement: Административное обновление пользователя
API SHALL allow an authenticated `analyst` or `admin` to use `PATCH /users/{user_id}/role` to update one or more of the target user's `role`, `department_id`, and `is_active` fields. The request SHALL be a partial update: omitted fields SHALL remain unchanged. `PATCH /users/me` SHALL continue to reject attempts to set `role` or `is_active`.

#### Scenario: Администратор меняет отдел и активность пользователя
- **WHEN** authenticated analyst or administrator sends `PATCH /users/{user_id}/role` with a valid existing `department_id` and `is_active=false`
- **THEN** the API returns `200` with the target user's updated representation, retains the user's existing role, and preserves all other omitted fields

#### Scenario: Администратор меняет роль без затрагивания других полей
- **WHEN** authenticated analyst or administrator sends `PATCH /users/{user_id}/role` with only a valid `role`
- **THEN** the API returns `200`, changes only the role, and retains the target user's department and activity state

#### Scenario: Самообслуживание не повышает права
- **WHEN** a user sends `PATCH /users/me` containing `role` or `is_active`
- **THEN** the API returns `422` and does not modify the user

#### Scenario: Недостаточные права для административного обновления пользователя
- **WHEN** an unauthenticated caller or authenticated role other than analyst or admin sends `PATCH /users/{user_id}/role`
- **THEN** the API returns the role-policy error and does not modify the target user
