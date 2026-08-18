## Context

См. `proposal.md - Why` про причину рассинхрона. Дополнительные факты,
важные для реализации и не входящие в спеку (внутренние детали):

- **Это не новая работа, а восстановление уже сделанной и принятой.**
  `src/bp1/REFACTORING_PLAN.md` (Шаг 18 «Реализовать форму (POST) и
  переформулировки в `SearchUrlProber`», Шаг 19 «Интегрировать
  `SearchUrlProber` с `SourceRegistrationService`») и `src/bp1/TODO.md`
  (строки 238, 264, оба отмечены `[x]`) фиксируют, что POST-форма,
  переформулировки и health-check при регистрации уже были реализованы
  и покрыты тестами — коммиты `af4b8d4` (Шаг 18) и `c786e15` (Шаг 19).
  Именно под эту, уже принятую версию API писаны `sources.py`/
  `runner/core.py`/`runner/probing.py`, переживший мерж. Задача этого
  изменения — перенести реализацию Шага 18 в текущий, более новый
  `search_probe.py` (`3731018`), а не спроектировать POST-пробинг с
  нуля.
- **Исторический баг, который план явно называет «серьёзнее, чем в
  постановке», в текущем коде не воспроизводится.** В версии `af4b8d4`
  параметрический перебор строил URL через
  `base_url.replace('{q}', param)`, подставляя ИМЯ параметра на место
  ЗНАЧЕНИЯ (`?text=q` вместо `?text=Название`) — все параметрические
  попытки проваливались молча. Текущий `build_probe_url` (этот файл,
  строка ~477) строит URL иначе: разбирает query-строку и заменяет
  любой ключ из `_DEFAULT_PARAM_CHAIN` на `{query_param}={value}` —
  структурно не может подставить имя параметра вместо значения. Чинить
  этот баг заново не нужно, но стоит держать в голове как пример того,
  чего эта переделка ДОЛЖНА избежать.
- **POST-транспорт `af4b8d4` (`_probe_form`) не парсит HTML-форму
  вообще** — он безусловно шлёт POST на `_search_endpoint(base_url)`
  (URL без query-строки) с телом `{param: search_query}`, как только
  GET-параметры не дали выдачи, независимо от того, найдена ли на
  странице реальная `<form>`. Текущий `search_probe.py` (после мержа)
  уже инвестировал в `extract_form_param(html, base_url)` — разбор
  настоящей HTML-формы (имя поля, `action`). Это изменение **сохраняет
  этот, более точный, путь** (POST только когда реально найдена форма
  с `method="post"`, на её `action_url`), а не откатывается к слепой
  POST-попытке `af4b8d4` — см. Decision 3. Меньше лишних запросов к
  сайтам, которым POST не нужен.
- Тесты Шага 18 (`tests/bp1/adaptive/test_search_probe.py` в `af4b8d4`:
  `test_probe_form_skipped_without_post_transport`,
  `test_probe_form_post_success`, ещё 5 обновлённых на исправление
  `{q}`-бага) в текущей ветке отсутствуют — файл тоже откатился вместе
  с `search_probe.py`. Сценарии из них переиспользуются как основа для
  новых тестов (см. `tasks.md`), адаптированные под HTML-form-driven
  POST вместо безусловного.

- Текущий `search_probe.py` (после мержа) — **асинхронный от начала до
  конца**: `probe()` — `async def`, делает `html = await fetch(url)`
  напрямую, без `asyncio.to_thread`. Это осознанно проще старой версии
  (коммит `af4b8d4`), где `probe()` был синхронным, а `probe_async()` —
  обёртка через `asyncio.to_thread` с таймаутом. Возвращаться к
  синхронному `probe()` не нужно — асинхронный вариант уже правильно
  работает в боевом пути (`runner/core.py:442`).
- `ProbeAttempt`/`ProbePlan` (текущий файл) — не то же самое, что было в
  `af4b8d4`. Сейчас `probe()` возвращает `ProbePlan` (список попыток +
  `winner`), а не `ProbedUrl | None`. Вызывающий код из `develop`
  (`sources.py:352`, `runner/probing.py:217`) писан под старый метод
  `probe_async()`, который возвращал именно `ProbedUrl | None` напрямую.
- `runner/probing.py` уже содержит `_default_probe_fetch` и
  `_default_probe_post` (реальные GET/POST через `urllib`,
  добавлены коммитом `af4b8d4` для старого синхронного дизайна) — они
  синхронные (`def`, не `async def`). Если подставить их как есть в
  качестве `fetch=`/`post=` для нынешнего `async def probe()`, первый же
  `await fetch(url)` упадёт с `TypeError: object str can't be used in
  'await' expression'` — на этапе первого реального пробинга, а не
  конструирования. Это отдельная, ещё не проявившаяся поломка на том же
  пути, и её нужно закрыть в этом же изменении, иначе `add-source`
  повторно упадёт сразу после того, как конструктор перестанет падать.
- `extract_form_param(html, base_url)` (текущий файл, строка ~434)
  извлекает `(query_param, action_url)` из первой найденной `<form>`, но
  **не** извлекает атрибут `method` — форма всегда доигрывается GET-ом
  через `fetch(build_probe_url(...))`. Ни одного теста, фиксирующего
  сигнатуру этой функции напрямую, нет (`tests/bp1/adaptive/
  test_search_probe.py` её не импортирует) — менять сигнатуру безопасно.

## Goals / Non-Goals

**Goals:**
- `AdaptiveRunner()` и `SourceRegistrationService.probe_search_endpoint`
  снова конструируются и отрабатывают без исключений конфигурации.
- Обнаруженная форма поиска с `method="post"` реально отправляется
  POST-ом (а не молча выполняется как GET и не имитируется).
- `looks_like_search_results` — инжектируемая (с дефолтом на текущую
  модульную функцию), как было задумано в `develop`.
- `sources.py:352` и `runner/probing.py:217` продолжают получать
  `ProbedUrl | None` — их код не переписывается под `ProbePlan`.
- Реальный `fetch`/`post` по умолчанию (`_default_probe_fetch`/
  `_default_probe_post`) действительно awaitable и не блокирует event
  loop дольше времени одного `urllib`-запроса.

**Non-Goals:**
- Не меняется логика перебора query-параметров, реформулировок и
  скоринга присутствия цели (`score_target_presence`,
  `find_matched_target_variant`) — она уже совместима с текущими
  вызывающими сторонами.
- Не меняется публичный контракт `AdaptiveRunner.run_task` /
  `SourceRegistrationService.register` — только их внутренняя
  работоспособность.
- Не добавляется поддержка нескольких форм на странице или форм с
  дополнительными скрытыми полями сверх найденного текстового
  input — сохраняется прежнее упрощение «первая подходящая форма,
  одно поле».

## Decisions

**1. `SearchUrlProber.__init__` получает обратно `post` и
`looks_like_search_results`, оба опциональные.**
```python
def __init__(
    self,
    param_chain: tuple[str, ...] = _DEFAULT_PARAM_CHAIN,
    fetch: Any = None,
    post: Any = None,
    looks_like_search_results: Callable[[str], bool] | None = None,
    logger_: logging.Logger | None = None,
):
    ...
    self._post = post
    self._looks_like = looks_like_search_results or looks_like_search_results_default
```
Альтернатива — сделать оба обязательными (как было задумано в
`af4b8d4` для `fetch`/`looks_like`, поднимавшими `NotImplementedError`
из заглушек) — отклонена: текущий `probe()` уже вызывается с одним
`fetch=` без `post`/`looks_like` в нескольких местах (например,
`core.py:127`, до того как он перезаписывается), обязательность сломает
эти случаи и не даёт ничего сверх дефолта.

**2. `extract_form_param` возвращает метод формы третьим элементом.**
`(query_param, action_url, method)`, где `method` — `'GET'` или
`'POST'` (значение атрибута `<form method="...">`, регистронезависимо;
отсутствие атрибута — `'GET'` по умолчанию, как в HTML-спеке). Один
вызов, у которого меняется сигнатура (строка ~803) — не отдельная
функция, чтобы не парсить HTML дважды.

**3. В `probe()` POST-ветка формы использует `self._post`, а не
`fetch`, и целится в реальный `action_url` формы.** `form_url =
action_url or base_url` (используем то, что вернул расширенный
`extract_form_param` из Decision 2 — сейчас `action_url` извлекается,
но отбрасывается как `_form_action`). Если `method == 'POST'`:
- есть `self._post` → `html = await self._post(form_url, {form_param:
  search_query})`, попытка помечается `kind='form'`, `method='POST'`;
- нет `self._post` → попытка сразу помечается `ok=False,
  detail='no_post_transport'`, `fetch`/`build_probe_url` для неё не
  вызываются (никакой имитации GET-ом).

Если `method == 'GET'` — поведение не меняется (нынешний
`fetch(build_probe_url(...))`).

Альтернатива — как в `af4b8d4::_probe_form`: слать POST безусловно на
`_search_endpoint(base_url)` (без query-строки) с телом
`{preferred_or_first_param: search_query}`, вообще не разбирая HTML на
предмет реальной формы — отклонена. Текущий код уже парсит форму для
GET-варианта; условие «POST только если реально найден
`method="post"`» даёт меньше лишних запросов к сайтам без формы вообще
и целится в её настоящий `action`, а не в угаданный эндпоинт.

**4. `ProbeAttempt`/`ProbePlan.add()` получают поле `method: str =
'GET'`.** Нужно, чтобы восстановленный `probe_async()` (см. п.5) мог
заполнить `ProbedUrl.search_method`. `params: dict[str, str]` не
добавляется — `ProbedUrl.search_params` для формы заполняется как
`{form_param: search_query}` в момент постройки `ProbedUrl`, а не
хранится в `ProbeAttempt` (избегаем раздувать датакласс полем, нужным
только одному потребителю).

**5. Восстанавливается `probe_async()` как тонкая обёртка над
`probe()`, без `asyncio.to_thread`.** Та же идея, что и
`probe_async`/`_attempt_to_probed` в `af4b8d4` (низкоуровневый перебор
+ обёртка, конвертирующая победителя в `ProbedUrl`), но без
поточной обёртки — она была нужна там только потому, что `probe()` был
синхронным; здесь `probe()` уже нативно `async`.
```python
async def probe_async(
    self, base_url, search_query, *, prefer_param=None,
    target_name='', target_inn='', source_type=None,
) -> ProbedUrl | None:
    plan = await self.probe(
        base_url, search_query, prefer_param=prefer_param,
        target_name=target_name, target_inn=target_inn,
        source_type=source_type,
    )
    if plan.winner is None:
        return None
    return ProbedUrl(
        source_name=target_name or search_query,
        search_url=plan.winner.url,
        search_method=plan.winner.method,
        confidence=1.0 if plan.winner.target_found else 0.5,
    )
```
Это даёт `sources.py:352` и `runner/probing.py:217` рабочий метод с
той сигнатурой и тем типом возврата, под который они уже написаны —
**ни один из этих двух вызывающих файлов не редактируется**. Альтернатива
(переписать оба места под `ProbePlan`, как уже сделано в
`core.py:442`) отклонена — это дублирует логику извлечения победителя
в трёх местах ради экономии одного маленького метода.

**6. `runner/core.py.__init__` — убрать первое (мёртвое) присваивание
`self._prober`, оставить только второе (строки 139-143), теперь
рабочее.** Никакой логики не меняется, просто убирается лишняя
инструкция, которая раньше маскировала (перезаписывала) битую версию.

**7. `_default_probe_fetch`/`_default_probe_post`
(`runner/probing.py`) становятся `async def`, оборачивая существующий
блокирующий `_probe_request` через `asyncio.to_thread`.** Сигнатура
вызова со стороны `SearchUrlProber` не меняется (`await fetch(url)`,
`await post(url, params)`), меняется только тело: блокирующий `urllib`
уходит в поток, event loop не блокируется на время сетевого запроса.
`_default_looks_like` остаётся синхронным (чистая проверка, не I/O,
`probe()` её не awaitит).

## Risks / Trade-offs

- [Изменение сигнатуры `extract_form_param`] → единственный вызов
  внутри того же файла, тесты сигнатуру напрямую не фиксируют —
  низкий риск, проверяется прогоном `tests/bp1/adaptive/
  test_search_probe.py`.
- [Реальный POST на боевые сайты при `probe_search=True`] → это и есть
  цель восстановления (сайты, где поиск только через форму, начинают
  находиться), но увеличивает число исходящих запросов на один при
  регистрации источника. Риска регрессии для существующих источников
  нет — POST выполняется, только если найдена форма именно с
  `method="post"` и словарные GET-параметры не дали выдачи.
- [`ProbedUrl.confidence` из `probe_async()` — эвристика 1.0/0.5] →
  не хуже старого поведения (в `af4b8d4` `confidence` тоже не было
  честной калибровкой), но стоит явно отметить: доверие приблизительное,
  не пересчитывается по `target_score`. Если понадобится точность —
  отдельное изменение.

## Open Questions

Нет — POST-транспорт по умолчанию (`_default_probe_fetch`/
`_default_probe_post`) уже существует и требует только исправления на
`async`, отдельного архитектурного решения принимать не нужно.
