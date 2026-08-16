## Why

В `src/bp1/` слоями лежит код от нескольких итераций разработки: новый адаптивный парсинг (`adaptive/`, ~250 КБ), каркас специализированных сборщиков (`collectors/`, 10 подпапок) и обвязка вокруг них. Работает из этого не всё: семь из десяти подпапок `collectors/` — пустые `__init__.py` по 50-90 байт, один сборщик на 2.9 МБ не подключён ни к чему, кроме собственных тестов, а MCP-сервер реализует внешний протокол, который в проекте никто не запускает.

Отдельно от мёртвого кода — нарушение единого источника правды по конфигурации: часть модулей `adaptive/` читает переменные окружения напрямую через `os.getenv()` в обход `core.config.settings`, а `processing/llm.py` содержит собственный самописный разбор `.env`. При этом соседние модули того же пакета (`adaptive/runner.py`, `integration/runner.py`, `processing/parser.py`) уже работают через `settings` — перевод начат, но не закончен.

Чистить нужно после подключения реального сбора (`connect-real-bp1-parsing`), а не до: пока сбор не запущен по-настоящему, нельзя быть уверенным, что именно из этого кода реально используется.

## What Changes

- **Удаляются пустые заготовки сборщиков** — `collectors/fips_rpa`, `google_news_rpa`, `hh_api`, `vk_api`, `zakupki_rpa`, `nic_ru_rpa`, `kodik_forum_rpa`: в каждой только `__init__.py` без реализации. Источники, под которые они заводились, остаются в `core/data/source.csv` и обрабатываются универсальным адаптивным парсером — отдельные адаптеры под них не написаны и не планируются в текущей итерации.
- **Удаляется `collectors/kad_arbitr_rpa`** (2.9 МБ, из них 2.8 МБ — записанные HTML-страницы в `tests_site/`): не зарегистрирован в `ParserFactory`, вызывается только собственными `test_headless.py`/`test_visible.py`. Правятся упоминания в `PREDPROD_README.md` и `src/bp1/README.md`, включая пример импорта `KadArbitrParser`.
- **Удаляется MCP-сервер** — `adaptive/integration/mcp_server.py` и его тест `tests/bp1/adaptive/test_mcp.py`: самописная реализация протокола обмена с AI-агентами (библиотеки `mcp` в зависимостях нет), к конвейеру отношения не имеет и никем не запускается. Вычищаются реэкспорты из `adaptive/__init__.py` и упоминание в `adaptive/integration/__init__.py`; схема `MCPTool` удаляется, если после этого не остаётся потребителей.
- **Конфигурация переводится на `core.config.settings`** — `adaptive/processing/llm.py` (включая удаление самописного разбора `.env`), `adaptive/cli.py` (убирается собственный вызов `load_dotenv`), `adaptive/llm_test.py`. Ключи и параметры LLM для BP-1 становятся полями `Settings`, как у остальных этапов.
- **Пересматриваются отладочные скрипты** — `src/bp1/test_parser.py` и `adaptive/llm_test.py` лежат в пакете исходного кода, а не в `tests/`, и запускаются вручную. Решается их судьба: перенести в `tests/`, оставить как есть с пояснением в докстринге, или удалить.

Явно НЕ удаляются: `collectors/stealth` (обход антибот-защиты, вызывается из `adaptive/strategies/engines.py` и обоих RPA-сборщиков), `collectors/fedresurs_rpa` (подключён через `parsers/fedresurs_adapter.py` и `ParserFactory`), `core/data/*.csv` (боевая конфигурация источников, конкурентов и задач сбора).

## Capabilities

Изменений в поведении конвейера нет: удаляется код, который ни один этап не вызывает, и меняется способ чтения уже существующих настроек, а не их смысл. Спеки не затрагиваются — `.openspec.yaml` получает `skip_specs: true`.

### New Capabilities
_нет_

### Modified Capabilities
_нет_

## Impact

- Код: удаление 8 подпапок `src/bp1/collectors/`, `adaptive/integration/mcp_server.py`, `tests/bp1/adaptive/test_mcp.py`; правки в `adaptive/__init__.py`, `adaptive/integration/__init__.py`, `adaptive/schemas.py`, `adaptive/processing/llm.py`, `adaptive/cli.py`, `adaptive/llm_test.py`, `core/config.py`.
- Документация: `src/bp1/README.md`, `PREDPROD_README.md`.
- Объём репозитория: −3 МБ (в основном `kad_arbitr_rpa/tests_site/`).
- Зависимости: возможно освобождаются пакеты, нужные только удаляемому коду — проверяется отдельной задачей, `requirements.txt` правится по факту.
- Порядок: выполняется ПОСЛЕ `connect-real-bp1-parsing`, чтобы чистить проверенный в работе код.
- Не входит: наведение порядка в `.env`/`.env.example` и вынос параметров парсинга в настройки — отдельная задача (`centralize-parsing-settings`), эта только убирает обход `settings` там, где он уже есть.
