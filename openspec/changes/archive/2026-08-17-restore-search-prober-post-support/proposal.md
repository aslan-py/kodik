## Why

Мерж `4312120` "Resolve merge conflicts with develop" объединил ветку, в
которой `SearchUrlProber` был переписан на упрощённый API (`param_chain`,
`fetch`, `logger_`, единственный метод `probe()`), с веткой `develop`, чей
код (`AdaptiveRunner.__init__`, `AdaptiveRunner.bind_probe_fetch`,
`SourceRegistrationService._default_prober`/`probe_search_endpoint`) писан
под старый, более богатый API (`fetch=`, `looks_like_search_results=`,
`post=`, метод `probe_async()`). Разрешение конфликта оставило новый
`search_probe.py`, но не поправило вызывающий код под него — в результате
`AdaptiveRunner()` **не создаётся вообще** (`TypeError:
SearchUrlProber.__init__() got an unexpected keyword argument
'looks_like_search_results'`), а `python -m src.bp1.cli add-source`
падает на этом же месте. Это блокирует весь адаптивный контур сбора
(BP-1), а не только регистрацию источника.

## What Changes

- **BREAKING** (внутренний API, не публичный интерфейс приложения):
  `SearchUrlProber.__init__` снова принимает `post: Callable[[str,
  dict[str, str]], str] | None` (транспорт для отправки найденной
  поисковой формы через POST) и `looks_like_search_results: Callable[[str],
  bool] | None` (инжектируемая эвристика «похоже ли на выдачу», по
  умолчанию — текущая модульная функция `looks_like_search_results`).
- `SearchUrlProber.probe()` при обнаружении в HTML формы с методом POST
  вызывает переданный `post`-колбэк вместо повторного GET по тому же URL;
  если `post` не передан — шаг формы помечается `no_post_transport` и не
  имитируется GET-запросом (поведение из коммита `af4b8d4`, потерянное при
  мерже).
- Вызывающий код приводится к единственному, реально существующему методу
  `probe()`:
  - `src/bp1/adaptive/integration/sources.py::probe_search_endpoint` —
    `prober.probe_async(...)` → `prober.probe(...)`.
  - `src/bp1/adaptive/integration/runner/probing.py::_get_or_probe_url` —
    `self._prober.probe_async(...)` → `self._prober.probe(...)`.
- `AdaptiveRunner.__init__` и `SourceRegistrationService._default_prober`
  собирают `SearchUrlProber` с восстановленными `post=`/
  `looks_like_search_results=` без падения; в `AdaptiveRunner.__init__`
  убирается мёртвое дублирующее присваивание `self._prober` (было два
  подряд — первое сразу перезаписывалось вторым, битым).
- `AdaptiveRunner.bind_probe_fetch` (используется тестами/браузерным
  транспортом для подмены загрузчика) снова успешно создаёт
  `SearchUrlProber` с переданными `fetch`/`looks_like`/`post`.

## Capabilities

### New Capabilities
- `bp1/adaptive-search-probing`: контракт `SearchUrlProber` — перебор
  query-параметров, детект и POST-отправка HTML-формы поиска,
  реформулировки запроса, инжектируемые `fetch`/`post`/эвристика
  «похоже на выдачу», и то, что вызывающий код (`AdaptiveRunner`,
  `SourceRegistrationService`) успешно строит проубер и получает от него
  план перебора.

### Modified Capabilities
(нет — существующий `bp1/adaptive-collection-run` не описывает пробинг
поисковых URL, поведение обхода источников и дедупликации не меняется)

## Impact

- `src/bp1/adaptive/integration/search_probe.py` — конструктор и `probe()`.
- `src/bp1/adaptive/integration/runner/core.py` — `AdaptiveRunner.__init__`.
- `src/bp1/adaptive/integration/runner/probing.py` — `bind_probe_fetch`,
  `_get_or_probe_url`.
- `src/bp1/adaptive/integration/sources.py` — `_default_prober`,
  `probe_search_endpoint`.
- Тесты: `tests/bp1/adaptive/test_search_probe.py`,
  `tests/bp1/adaptive/test_runner_source_aware.py`,
  `tests/bp1/adaptive/test_source_registration.py`,
  `tests/bp1/adaptive/test_runner_concurrency.py` — все напрямую строят
  `AdaptiveRunner()`, сейчас падают на конструкторе.
