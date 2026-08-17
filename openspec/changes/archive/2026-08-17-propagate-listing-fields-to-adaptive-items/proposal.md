## Why

BP-1 (адаптивный контур) сейчас пишет в `raw_data.items[]` `published_at=null`,
`region=null` и `media_name=<URL источника>` для абсолютно всех собранных
новостей — независимо от того, есть ли у источника реальная разметка для этих
полей. Данные при этом физически извлекаются: `_extract_by_selectors()`
(`processing/parser/selectors.py`) находит `published_at`/`region`/
`media_name` не хуже, чем `url`/`title` — но `_page_items()`
(`pagination.py:76-146`) возвращает наружу только `(title, url)`, а
`bridge.py` при промоушене в `ParsedItem` жёстко пишет `published_at=None`,
`region=None` и наследует `media_name` от URL источника.

Отдельно от этого система тратит деньги на два LLM-вызова, единственный
результат которых — данные, оседающие исключительно в `extra`:
`AIAgent.score_relevance()` (батчами, `RELEVANCE_PROMPT`) и
`AIAgent.enrich_event()` (по одному вызову на новость, `ENRICHMENT_PROMPT`,
извлекает `published_at`/`author`/`keywords`/`summary`/`mentioned_company`/
`mentioned_inn`/`sentiment`). По прямому решению (`extra` для новостей всегда
остаётся `{}`) результат обоих вызовов гарантированно никуда не попадает —
это чистая трата LLM-бюджета без выхода.

По прямому указанию: `title`/`url`/`published_at`/`region`/`media_name`
обязаны заполняться сразу при сборе (без LLM на каждый элемент), `extra`
остаётся пустым, лишних LLM-запросов, тратящих деньги на данные для `extra`,
быть не должно.

Отдельно уточнено и закрыто по ходу расследования:
- `meta.items_count`/`meta.empty_reason` — **оставляем как есть**, добавлены
  коллегой сознательно (коммит `a137289`), вне рамок этого изменения.
- Раздел `metrics` уже не попадает в persisted JSON (`exclude=True`,
  коммит `9fb12e8`, подтверждено на свежих строках БД) — кода здесь менять
  не требуется.

## What Changes

- `_page_items()`/`_extract_by_selectors()` перестают отбрасывать
  `published_at`/`region`/`media_name`, извлечённые селекторами адаптера на
  уровне страницы листинга — эти значения протаскиваются через
  `_collect_news_with_pagination()`/`_run_extraction_cascade()` до итогового
  элемента новости (как `ex_published_at`/`ex_region`/`ex_media_name`).
- При промоушене новости в `ParsedItem` (`bridge.py`) `published_at`/
  `region`/`media_name` читаются из этих значений; если данных нет —
  остаются `null` (никакого LLM-фолбэка и никакой URL-заглушки для
  `media_name`).
- Удаляются: `RelevanceFilter` (`processing/relevance.py`),
  `AIAgent.score_relevance`/`_score_relevance_batch`/`enrich_event`
  (`processing/llm/agent.py`), промпты `RELEVANCE_PROMPT`/`ENRICHMENT_PROMPT`
  (`processing/_llm/prompts.py`), вызовы `self._relevance.apply(...)`/
  `_enrich_news(...)` в `AdaptiveParser._assemble_items`
  (`processing/parser/core.py`).
- Удаляются связанные настройки: `bp1_relevance_mode`,
  `bp1_relevance_threshold`, `bp1_enrichment_enabled` (`core/config.py`) и
  производные константы (`processing/parser/constants.py`,
  `processing/_llm/constants.py`).
- `extra` для промотированных новостей остаётся `{}` — без изменений.
- `meta.items_count`/`meta.empty_reason` — без изменений (сознательно вне
  рамок).
- Раздел `metrics` — без изменений в коде (уже не сериализуется).

## Capabilities

### New Capabilities

_(нет)_

### Modified Capabilities

- `bp1/adaptive-collection-run`: добавляется требование о том, что элементы
  сырьевого слоя обязаны нести собственные `published_at`/`region`/
  `media_name` источника, извлечённые непосредственно на этапе сбора (без
  LLM per-item), а не системные заглушки (`null`/URL источника).

## Impact

- `src/bp1/adaptive/processing/parser/pagination.py` — `_page_items()`,
  `_make_item()`, `_make_search_page_item()`.
- `src/bp1/adaptive/processing/parser/core.py` — `_collect_news_with_pagination`,
  `_run_extraction_cascade`, `_assemble_items`; удаление `_enrich_news`,
  `self._relevance`, `self._enrichment_enabled`.
- `src/bp1/adaptive/integration/bridge.py` — промоушен `extra.news[]` →
  `ParsedItem`.
- `src/bp1/adaptive/processing/relevance.py` — файл удаляется целиком.
- `src/bp1/adaptive/processing/llm/agent.py` — удаление методов
  `score_relevance`/`_score_relevance_batch`/`enrich_event`.
- `src/bp1/adaptive/processing/_llm/prompts.py` — удаление
  `RELEVANCE_PROMPT`/`ENRICHMENT_PROMPT`.
- `src/bp1/adaptive/processing/_llm/constants.py`,
  `src/bp1/adaptive/processing/parser/constants.py` — удаление констант,
  специфичных только для relevance/enrichment (батч-размер, лимиты токенов,
  порог).
- `core/config.py` — удаление `bp1_relevance_mode`/`bp1_relevance_threshold`/
  `bp1_enrichment_enabled`.
- Тесты: `tests/bp1/adaptive/test_parser.py`,
  `tests/bp1/adaptive/test_integration.py`, `tests/bp1/adaptive/test_llm.py`
  (удаление тестов на батчинг relevance/enrichment, обновление тестов
  промоушена).
- Не затрагивает классический RPA-контур (`fedresurs_rpa/parser.py`) — там
  эти поля уже собираются напрямую из извлечённых данных, LLM на `extra` не
  тратится.
- Не затрагивает `meta` (`items_count`/`empty_reason` остаются) и раздел
  `metrics` (уже не сериализуется, код не меняется).
