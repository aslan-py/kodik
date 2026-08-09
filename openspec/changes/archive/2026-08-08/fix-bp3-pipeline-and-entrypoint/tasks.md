## 1. Общий sync-модуль БД для BP-3

- [x] 1.1 Создать `src/bp3/db.py` — перенести туда `DATABASE_URL`/`engine`/`Session` из `fetch_data.py` (тот же код, без изменений)
- [x] 1.2 `fetch_data.py` — заменить локальную сборку на импорт из `src/bp3/db.py`
- [x] 1.3 `save_results_module.py` — заменить локальную сборку на импорт из `src/bp3/db.py`

## 2. Синтаксис и импорты `save_results_module.py`

- [x] 2.1 Починить отступ блока «4. Сохраняем найденные источники» — вынести его из цикла `for news_id, fields in data_by_id.items()`, выполнять один раз после цикла (до `session.commit()`)
- [x] 2.2 Добавить `from src.bp7.models import SourceCandidate`
- [x] 2.3 Прогнать `python -m py_compile src/bp3/modules/save_results_module.py` — убедиться, что файл валиден
- [x] 2.4 Прогнать `python -c "import core.pipeline.registry"` — убедиться, что цепочка импортов больше не падает

## 3. Синхронизация `run_bp3()` с актуальным списком модулей

- [x] 3.1 В `src/bp3/pipeline.py::run_bp3()` добавить `ExpectedResultModule()` в список `Pipeline([...])` (после `GenerationTaskModule()`, перед `SourceFinderModule()` — как в текущем `main.py`)
- [x] 3.2 Поправить `domains_found` в возвращаемой сводке — считать суммарное число найденных доменов по всем конкурентам (`sum(len(v.get('sources', [])) for v in (result.domains_to_add or {}).values())`), а не число ключей словаря

## 4. Единая точка входа

- [x] 4.1 В `src/bp3/pipeline.py` раскомментировать/актуализировать блок `if __name__ == '__main__':` — по образцу `src/bp2/pipeline.py` (блок уже был активен, актуализировал докстринг модуля)
- [x] 4.2 Проверить, что нигде в проекте (README, скрипты, CI) нет ссылок на `python main.py` в корне (нашёл и поправил `src/bp3/README.md`; `api/main.py` и `api/API_README.md`/`FASTAPI_PLAN.md` — другой, не связанный файл, не трогал)
- [x] 4.3 Удалить корневой `main.py`

## 5. Докстринги

- [x] 5.1 Добавить докстринги классам и методам `process()`/`__init__()` в: `action_planning_module.py`, `comment_action_module.py`, `expected_result_module.py`, `generation_task_module.py`, `source_finder_module.py`, `save_results_module.py`, `config.py::get_llm()`

## 6. Снять лимит записей за прогон

- [x] 6.1 В `src/bp3/fetch_data.py::fetch_data()` убрать `.limit(10)` из выборки `normalized_item`
- [x] 6.2 Проверить `fetch_news_stats()` в том же файле — тот же лимит там не продублирован (сейчас `.limit` только в одном месте, сверить при правке)

## 7. Настройки через pydantic

- [x] 7.1 В `core/config.py::Settings` добавить поля: `openrouter_api_key: str`, `tavily_api_key: str`, `bp3_model: str = 'openai/gpt-4o'` (дефолт — текущий `DEFAULT_MODEL` из `src/bp3/config.py`; имя поля уточнить при реализации, чтобы не путать с другими `*_model` в проекте)
- [x] 7.2 `src/bp3/config.py::get_llm()` — читать `settings.openrouter_api_key`/`settings.bp3_model` вместо `os.getenv('OPENROUTER_API_KEY')`/`os.getenv('MODEL', DEFAULT_MODEL)`
- [x] 7.3 `src/bp3/pipeline.py::run_bp3()` — проверка ключей через `settings.openrouter_api_key`/`settings.tavily_api_key` вместо `os.getenv(...)`
- [x] 7.4 `src/bp3/modules/source_finder_module.py` — `TavilyClient(api_key=...)` через `settings.tavily_api_key` вместо `os.getenv('TAVILY_API_KEY')` на уровне модуля
- [x] 7.5 Проверить `.env`/`.env.example` — переменные `OPENROUTER_API_KEY`/`TAVILY_API_KEY` уже там есть (сверено), `MODEL`/`BP3_MODEL` добавить в `.env.example`, если заводим поле с явным дефолтом в `.env`

## 8. Проверка вручную

- [x] 8.1 Прогнать `python -m src.bp3.pipeline` на данных, которые уже есть в `normalized_item` (без запуска BP-1) — убедиться, что `categorized_event.task`/`expected_result` заполняются, `source_candidate` наполняется без дублей
- [x] 8.2 Прогнать этап 3 через `core/pipeline/cli.py`/админку — сверить, что результат идентичен ручному запуску (тот же список модулей, та же проверка ключа)
- [x] 8.3 Убедиться, что при отсутствии `OPENROUTER_API_KEY`/`TAVILY_API_KEY` в `.env` `Settings` падает при старте (pydantic сам проверит обязательные поля) — старое сообщение `ValueError`/`RuntimeError` из `get_llm()`/`run_bp3()` больше не нужно как единственная защита
