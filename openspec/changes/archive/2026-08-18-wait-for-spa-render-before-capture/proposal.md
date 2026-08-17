## Why

`StealthStrategy.fetch()` ([engines.py:103-148](src/bp1/adaptive/strategies/engines.py:103))
читает `page.content()` сразу после `page.goto()`, не дожидаясь
асинхронно подгружаемого контента. Для SPA-источников (rbc.ru и
подобные — `is_spa=True` в классификации) результаты поиска
подгружаются отдельным JS-запросом уже ПОСЛЕ события `load`, поэтому
STEALTH стабильно получает «оболочку» страницы (навигация, курсы валют,
рубрики, футер), а не искомый контент. При этом `StrategyResult.success`
считается только по размеру HTML (`len(html) >= MIN_CONTENT_LENGTH`), а
не по наличию реального контента — оболочка достаточно большая (~350
КБ), поэтому репортится как успех.

Диагностировано на реальном прогоне (change `fix-search-probe-antibot-fetch`,
задача 5.3): и `q=`, и `query=` кандидаты пробинга rbc.ru получили через
STEALTH ~350 КБ контента без единого упоминания искомого конкурента.
Сохранённые снимки (`src/bp1/data/html_pages/https___rbc.ru__*.html`) за
13 разных прогонов имеют почти одинаковый размер независимо от
параметра/конкурента — верный признак, что каждый раз захватывается одна
и та же оболочка, а не результат конкретного запроса.

У соседней стратегии `BrowserStrategy`
([orchestrator.py:313-426](src/bp1/adaptive/strategies/orchestrator.py:313))
похожая проблема частично решена через `_wait_for_results_container`/
`_wait_for_any_links` — но её селекторы (`ul.search-results__list li` и
т.п.) заточены под другой сайт (судя по комментарию — Lenta.ru) и не
проверялись на rbc.ru: `has_captcha=True` у rbc.ru исключает
`BrowserStrategy` из допустимых стратегий (`_ALLOWED_STRATEGIES_TABLE`),
она для него ни разу не выполнялась. А запасной вариант
(`_wait_for_any_links`, порог `MIN_LINK_COUNT_FOR_CONTENT=3`) слишком
слабый: в самой «оболочке» rbc.ru уже 369 ссылок (нав/футер/курсы), порог
проходит мгновенно, ничего реально не ожидая.

**`StealthStrategy` менять нельзя** — она используется для fedresurs.ru,
трогать её сейчас не будем (решение по риску). Значит фикс не может быть
правкой существующего класса.

## What Changes

- Новый класс стратегии (копия `StealthStrategy`, не правка) для
  источников, отличных от fedresurs.ru — с ожиданием
  `page.wait_for_load_state('networkidle')` после `page.goto()`, прежде
  чем читать `page.content()`. `networkidle` выбран как основной сигнал
  (не привязан к селекторам конкретного сайта — ждёт, пока сетевые
  запросы устаканятся, что универсально указывает на «JS догрузил
  данные»), а не копирование селекторного механизма `BrowserStrategy`,
  который для rbc.ru не проверялся и, вероятно, не сработает.
- Новый `StrategyType` для этой стратегии и её регистрация в
  `build_default_strategies()`.
- Маршрутизация: источники с `has_captcha`/`is_spa` (кроме fedresurs.ru,
  который не проходит через этот контур вовсе — использует отдельный
  `fedresurs_rpa` со своим `BrowserManager`) должны попадать на новую
  стратегию вместо старой `StealthStrategy`. `StealthStrategy` остаётся
  зарегистрированной и рабочей как есть, просто перестаёт быть тем, на
  что реально маршрутизируются антибот+SPA источники (кроме
  fedresurs.ru, если он когда-либо пойдёт через этот контур).

## Capabilities

### New Capabilities

- `bp1/adaptive-degradation-strategies`: поведение стратегий обхода
  деградационной лестницы (FAST/CRAWL4AI/BROWSER/WAYBACK/STEALTH/HITL) —
  в частности, обязанность дожидаться реально отрисованного контента на
  JS-рендерящих стратегиях перед тем, как считать fetch успешным.
  Существующей capability под это поведение нет (`adaptive-collection-run`
  — про прогон сбора в целом, не про отдельную стратегию).

## Impact

- `src/bp1/adaptive/strategies/engines.py` — новый класс стратегии (копия
  `StealthStrategy`); сама `StealthStrategy` не редактируется.
- `src/bp1/adaptive/schemas.py` — новое значение `StrategyType`.
- `src/bp1/adaptive/strategies/orchestrator.py` — регистрация новой
  стратегии в `build_default_strategies()`, маршрутизация в
  `_ALLOWED_STRATEGIES_TABLE`/`_DEGRADATION_ORDER`.
- `tests/bp1/adaptive/test_orchestrator.py` — новые тесты на новую
  стратегию; существующие тесты `StealthStrategy` не меняются (она не
  тронута).
