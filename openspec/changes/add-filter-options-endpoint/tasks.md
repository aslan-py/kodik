## 1. Расширить фильтрацию action-items

- [ ] 1.1 Добавить необязательные `deadline: date` и `priority: str` в сигнатуру и OpenAPI-описание `GET /action-items`.
- [ ] 1.2 Провести новые параметры через service в CRUD, применяя точный deadline и conditional join с showcase для точного отображаемого priority.
- [ ] 1.3 Добавить CRUD/service/API-тесты отдельных и комбинированных `deadline`/`priority` фильтров, включая принудительный viewer scope своим отделом.

## 2. Реализовать получение вариантов

- [ ] 2.1 Добавить Pydantic-схемы `IdLabelOption`, секций showcase/action-items и общего ответа с точным контрактом spec.
- [ ] 2.2 Реализовать DISTINCT-запросы showcase для непустых category, region, competitor и department с детерминированной сортировкой.
- [ ] 2.3 Реализовать action-запросы для deadline, priority, assigned_user_id и department_id с joins подписей и SQL-ограничением viewer своим отделом.
- [ ] 2.4 Собрать service-ответ, используя полный порядок `П1`—`П4` для showcase и `open` → `in_progress` → `done` для action status.

## 3. Добавить единый endpoint

- [ ] 3.1 Добавить тонкий защищённый `GET /filter-options` с `ViewerDep`, response model и документированными `401`/`403`.
- [ ] 3.2 Зарегистрировать router и Swagger-тег в общей сборке API.
- [ ] 3.3 Обновить API-документацию примером ответа и пояснить ISO-даты и `{value, label}` для ID-backed фильтров.

## 4. Проверить контракт и безопасность

- [ ] 4.1 Добавить endpoint-тест точной структуры ответа, удаления null/пустых значений, дедупликации и стабильной сортировки.
- [ ] 4.2 Проверить пустую витрину и отсутствие action-items: data-derived массивы пусты, статические priority/status остаются заполнены.
- [ ] 4.3 Проверить `401` без токена, `403` для pending и успешные ответы viewer/analyst/admin.
- [ ] 4.4 Проверить, что viewer не получает сроки, приоритеты, пользователей и отделы из задач другого отдела, а analyst/admin получают общий набор.
- [ ] 4.5 Проверить, что каждое возвращённое action значение действительно применяется в соответствующем query-параметре списка.

## 5. Согласовать с общим endpoint-manifest

- [ ] 5.1 Если change `verify-and-stabilize-api-endpoints` уже применён, добавить `GET /filter-options` в его manifest и обновить ожидаемое число операций с 90 до 91.
- [ ] 5.2 Сгенерировать OpenAPI и подтвердить уникальный operationId, точную response schema и наличие новых action query-параметров.
- [ ] 5.3 Запустить `pytest tests/api`, статические проверки и полный `pytest`, устранив относящиеся к change регрессии.
