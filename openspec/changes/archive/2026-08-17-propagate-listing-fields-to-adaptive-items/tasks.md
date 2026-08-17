## 1. Уровень листинга — перестать терять извлечённые поля

- [x] 1.1 Расширить возврат `_page_items()` (`processing/parser/pagination.py`)
      так, чтобы вместе с `title`/`url_abs`/`url_rel` прокидывались
      `published_at`/`region`/`media_name`, уже извлечённые
      `_extract_by_selectors()` для того же элемента, когда они есть.
- [x] 1.2 Обновить вызывающий код `_page_items()` в
      `_collect_news_with_pagination()` (`processing/parser/core.py`) под
      новую форму возврата.
- [x] 1.3 В `_run_extraction_cascade()` (`processing/parser/core.py`)
      добавить в результирующий словарь `ex_published_at`/`ex_region`/
      `ex_media_name` — только когда значение реально пришло с листинга (не
      добавлять ключ, если значения нет).
- [x] 1.4 Обновить существующие тесты `test_page_items_*`
      (`tests/bp1/adaptive/test_parser.py`), которые распаковывают старую
      форму кортежа.

## 2. Промоушен в `ParsedItem` — использовать напрямую, без LLM-фолбэка

- [x] 2.1 В `bridge.py`, при сборке промотированного `ParsedItem` из
      `extra.news[]`, заменить `published_at=None` на
      `entry.get('ex_published_at')`.
- [x] 2.2 Заменить `region=None` на `entry.get('ex_region')`.
- [x] 2.3 Убрать фолбэк `media_name=base_media_name` (наследование от
      `raw_item.get('media_name')` служебной страницы поиска, равное URL
      источника) — заменить на `entry.get('ex_media_name')`, без
      URL-заглушки.
- [x] 2.4 Проверить, что `media_name` служебного элемента «страница поиска»
      (`_make_search_page_item`, `pagination.py:168`) не затронут.

## 3. Удалить LLM-вызовы, чей результат уходит только в `extra`

- [x] 3.1 Удалить `src/bp1/adaptive/processing/relevance.py`
      (`RelevanceFilter`) целиком.
- [x] 3.2 Удалить `score_relevance`/`_score_relevance_batch`/`enrich_event`
      из `AIAgent` (`processing/llm/agent.py`).
- [x] 3.3 Удалить `RELEVANCE_PROMPT`/`ENRICHMENT_PROMPT` из
      `processing/_llm/prompts.py`.
- [x] 3.4 В `AdaptiveParser` (`processing/parser/core.py`) убрать
      `self._relevance`, `self._enrichment_enabled` (конструктор),
      `_enrich_news()` целиком, и блок `filtered_news = await
      self._relevance.apply(...)` / вызов `_enrich_news(...)` в
      `_assemble_items`.
- [x] 3.5 Убрать из `core/config.py`: `bp1_relevance_mode`,
      `bp1_relevance_threshold`, `bp1_enrichment_enabled`.
- [x] 3.6 Убрать производные константы, специфичные только для
      relevance/enrichment, из `processing/parser/constants.py`
      (`RELEVANCE_MODE`, `RELEVANCE_THRESHOLD`, `ENRICHMENT_ENABLED`) и из
      `processing/_llm/constants.py` (`RELEVANCE_BATCH_SIZE`,
      `RELEVANCE_MAX_TOKENS`, `ENRICHMENT_MAX_TOKENS`,
      `DEFAULT_RELEVANCE_THRESHOLD`). Не трогать `run_limited`/
      `processing/_llm/chunking.py` — используется отдельно каскадом
      извлечения `text` (`LLMClient`), не только relevance.
- [x] 3.7 Удалить/обновить тесты, завязанные на удалённый код: батчинг
      relevance в `tests/bp1/adaptive/test_llm.py`, обогащение в
      `tests/bp1/adaptive/test_parser.py`.

## 4. Проверка

- [x] 4.1 `ruff check src/bp1` — 0 нарушений после удаления мёртвых
      импортов.
- [x] 4.2 Полный прогон `../.venv-kodik/Scripts/python.exe -m pytest tests/bp1/ -q`
      — без регрессий (за вычетом намеренно удалённых тестов из п. 3.7).
      429 passed, 10 failed — все 10 падений требуют живого Postgres
      (`test_source_registration.py`, `test_cli.py`,
      `test_search_task_coverage.py`; см. CLAUDE.md: «Тестам нужен живой
      Postgres»), Docker в этой среде не поднят — падения не связаны с
      правкой (до неё было 13 падений: те же 10 + 3 из-за `_deep_fetch`,
      которые эта правка и исправила).
- [x] 4.3 Живой прогон `python -m src.bp1.cli competitor "Сбербанк"`
      (Postgres поднят пользователем). Результат — `raw_1_20260817_202242.json`
      (lenta.ru) и `raw_2_20260817_202247.json` (rbc.ru), `raw_item_id=6,7`:
      - lenta.ru: `published_at` реально заполнен ("15:49", "10:51, 16
        августа 2026", ...) вместо `null`; `region`/`media_name` — `null`
        (адаптер не даёт для них селекторов) — БЕЗ URL-заглушки источника.
      - rbc.ru: `published_at`/`region`/`media_name` заполнены, но
        одинаковым "сырым" текстом узла категории — см. отдельную находку
        ниже, это не регресс правки.
      - `extra: {}` у всех items в обоих файлах.
      - `meta` содержит `items_count`/`empty_reason` без изменений.
      - `metrics` в выводе отсутствует (оба файла: только `meta`+`items`).
      - В логах прогона — только LLM-вызовы классификации/чанкинга текста
        статьи; вызовов `score_relevance`/`enrich_event` нет (их больше
        нет в коде).

**Находка сверх плана (не регресс, отдельный вопрос):** кэшированный
адаптер `rbc.ru` (`cache --show rbc.ru`, `confidence=0.263`,
`created_at=2026-08-15`) имеет ОДИН И ТОТ ЖЕ CSS-селектор
(`.search-item__category`) сразу для `published_at`, `region` и
`media_name` — поэтому все три поля честно получают одинаковый сырой
текст узла категории. Это не баг прокладки данных (эта правка), а
качество селекторов, выведенных `analyze_structure` при низкой
уверенности LLM — отдельная задача (например, сброс адаптера для
переразбора или валидация неразличимости полей при генерации селекторов).
