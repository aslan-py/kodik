## 1. `SearchUrlProber`: конструктор и инжектируемая эвристика

- [x] 1.1 В `search_probe.py::SearchUrlProber.__init__` добавить
      параметры `post: Any = None` и `looks_like_search_results:
      Callable[[str], bool] | None = None`; сохранить в `self._post` и
      `self._looks_like` (дефолт — модульная функция
      `looks_like_search_results`).
- [x] 1.2 Заменить прямые вызовы модульной `looks_like_search_results(html)`
      внутри `probe()` (три места: параметрический перебор, форма,
      реформулировки) на `self._looks_like(html)`.

## 2. Детект метода формы и реальный POST

- [x] 2.1 В `extract_form_param` добавить извлечение атрибута
      `method` тега `<form>` (регистронезависимо, по умолчанию `'GET'`);
      изменить возвращаемый тип на `tuple[str | None, str | None, str]`
      (`query_param, action_url, method`).
- [x] 2.2 Обновить единственный вызов `extract_form_param` в `probe()`
      под новую сигнатуру.
- [x] 2.3 В ветке «Цикл 1.5» (форма) `probe()`: если `method == 'POST'`
      и `self._post` задан — вызвать `await self._post(form_url,
      {form_param: search_query})`, где `form_url = action_url or
      base_url` (используем реальный `action` формы из задачи 2.1, а не
      слепой эндпоинт `_search_endpoint(base_url)`, как было в
      `af4b8d4`), вместо `fetch(build_probe_url(...))`; записать
      попытку с `method='POST'`.
- [x] 2.4 Там же: если `method == 'POST'`, а `self._post` не задан —
      записать попытку `ok=False, detail='no_post_transport'` без
      обращения к `fetch`, и перейти к реформулировкам (не выполнять
      GET по тому же адресу).
- [x] 2.5 Добавить полю `ProbeAttempt.method: str = 'GET'` и параметру
      `ProbePlan.add(..., method: str = 'GET')` — прокинуть значение из
      2.3 при записи form-попытки.

## 3. Возврат `probe_async()` с прежней сигнатурой

- [x] 3.1 Добавить в `SearchUrlProber` метод `async def probe_async(
      base_url, search_query, *, prefer_param=None, target_name='',
      target_inn='', source_type=None) -> ProbedUrl | None`,
      вызывающий `probe()` и конвертирующий `plan.winner` в `ProbedUrl`
      (`search_url=winner.url`, `search_method=winner.method`,
      `confidence=1.0 if winner.target_found else 0.5`); `None`, если
      `plan.winner` отсутствует.
- [x] 3.2 Убедиться, что `sources.py:352`
      (`SourceRegistrationService.probe_search_endpoint`) и
      `runner/probing.py:217` (`_get_or_probe_url`) вызывают именно
      `probe_async(...)` с теми же именованными аргументами, что уже
      написаны — без правок в этих двух файлах, кроме проверки, что
      вызов действительно совпадает с новой сигнатурой из 3.1.

## 4. Рабочие `fetch`/`post` по умолчанию — сделать awaitable

- [x] 4.1 В `runner/probing.py` превратить `_default_probe_fetch` и
      `_default_probe_post` в `async def`, обернув существующий вызов
      `_ProbingMixin._probe_request(...)` через `asyncio.to_thread`
      (сигнатура вызова снаружи не меняется, тело — блокирующий urllib
      уходит в отдельный поток).
- [x] 4.2 Проверить, что `_default_looks_like` остаётся синхронным и
      по-прежнему передаётся как `looks_like_search_results=` (не
      awaitится нигде в `probe()`).

## 5. Конструирование проубера в вызывающем коде

- [x] 5.1 В `runner/core.py::AdaptiveRunner.__init__` убрать первое
      (мёртвое) присваивание `self._prober = SearchUrlProber(fetch=
      self._fetch_content)` (строка ~127); оставить только второе
      присваивание с `fetch=`/`looks_like_search_results=`/`post=`
      (строки ~139-143) — теперь оно валидно после задачи 1.1.
      Дополнительно удалён сам метод `_fetch_content` — после удаления
      единственного присваивания он остался полностью неиспользуемым.
- [x] 5.2 В `sources.py::SourceRegistrationService._default_prober`
      убедиться, что вызов `SearchUrlProber(fetch=...,
      looks_like_search_results=..., post=...)` (строка ~323) больше не
      падает — конструктор уже принимает эти kwargs после задачи 1.1.
- [x] 5.3 В `runner/probing.py::_ProbingMixin.bind_probe_fetch` (строка
      ~130) убедиться, что переданные `fetch`/`looks_like`/`param_chain`/
      `post` действительно долетают до `SearchUrlProber.__init__` без
      ошибки. По ходу проверки найдено и исправлено: `bind_probe_fetch`
      зовёт конструктор с `param_chain=None`, когда вызывающая сторона
      передаёт только `fetch` (как в существующих тестах) — конструктор
      получил защиту `param_chain or _DEFAULT_PARAM_CHAIN` (см. задачу
      1.1), иначе `self._param_chain` стал бы `None` и `probe()` падал
      бы на `for p in self._param_chain`.

## 6. Проверка

- [x] 6.1 `../.venv-kodik/Scripts/python.exe -c "from
      src.bp1.adaptive.integration.runner import AdaptiveRunner;
      AdaptiveRunner()"` — конструктор не падает.
- [x] 6.2 `../.venv-kodik/Scripts/python.exe -m pytest
      tests/bp1/adaptive/test_search_probe.py
      tests/bp1/adaptive/test_source_registration.py
      tests/bp1/adaptive/test_runner_source_aware.py
      tests/bp1/adaptive/test_runner_concurrency.py -q` — все проходят.
      По ходу найдено 5 тестов `extract_form_param_*`, фиксирующих старую
      2-элементную сигнатуру напрямую (design.md ошибочно утверждал, что
      таких тестов нет) — обновлены под `(param, action, method)`, плюс
      добавлен `test_extract_form_param_detects_post_method`.
- [x] 6.3 Добавить/дополнить тест на POST-ветку в
      `test_search_probe.py`: форма с `method="post"` и настроенным
      `post=` даёт успешный `ProbeAttempt(kind='form', method='POST',
      ok=True)`; без `post=` — `detail='no_post_transport'`, `fetch`
      для этого адреса не вызывается (проверяется моком). За основу
      сценариев взять `test_probe_form_skipped_without_post_transport`
      и `test_probe_form_post_success` из `af4b8d4:tests/bp1/adaptive/
      test_search_probe.py` (`git show af4b8d4:tests/bp1/adaptive/
      test_search_probe.py`) — адаптировать под HTML с реальным
      `<form method="post">` (текущий дизайн шлёт POST только когда
      форма найдена, а не безусловно, как в том коммите).
      Добавлены `test_probe_form_post_success` и
      `test_probe_form_post_skipped_without_transport`.
- [x] 6.4 `python -m src.bp1.cli add-source https://www.lenta.ru/news`
      — ручной прогон, завершается без traceback. Реально нашёл рабочий
      GET-параметр `q` на lenta.ru и напечатал сводку регистрации.
- [x] 6.5 `../.venv-kodik/Scripts/python.exe -m ruff check
      src/bp1/adaptive/integration/search_probe.py
      src/bp1/adaptive/integration/sources.py
      src/bp1/adaptive/integration/runner/core.py
      src/bp1/adaptive/integration/runner/probing.py`.
      Также прогнан ruff на изменённом `tests/bp1/adaptive/
      test_search_probe.py` — одна строка длиннее 80 символов
      исправлена.
