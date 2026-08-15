"""Константы и лимиты AdaptiveParser."""

from __future__ import annotations

from core.config import settings

# Максимальное количество новостей, собираемых за один проход пагинации.
DEFAULT_MAX_NEWS = settings.bp1_max_news_per_source

# Сколько прогонов подряд закэшированный адаптер может не проходить
# контроль качества, прежде чем будет сброшен и выведен заново (Шаг 21
# плана рефакторинга). 2, а не 1: разовый провал бывает от самих данных
# (пустая выдача, дубли в источнике), а не от устаревших селекторов.
ADAPTER_FAIL_THRESHOLD = 2

# Верхний предел страниц пагинации на источник за прогон (Шаг 16 плана
# рефакторинга, REFACTORING_PLAN.md — T5). Раньше _max_pages() возвращал
# жёстко зашитое 10000 (фактически «без лимита»), и единственным тормозом
# был DEFAULT_MAX_NEWS — его рост напрямую удлинял прогон.
MAX_PAGINATION_PAGES = settings.bp1_max_pagination_pages

# Минимальная длина текста, при которой результат извлечения считается
# успешным (для каскада CSS → LLM → сниппет).
MIN_ARTICLE_TEXT_LENGTH = settings.bp1_min_article_text_length

# Максимальное количество одновременно докачиваемых статей (глубокий фетч).
MAX_CONCURRENT_FETCHES = settings.bp1_max_concurrent_fetches

# Таймаут (в секундах) на извлечение полного текста одной статьи. Защищает
# глубокий фетч от зависания на проблемной странице, чтобы медленная статья
# не занимала слот конкурентности и не лишала остальные новости полного
# текста (раньше первые 1-2 статьи «съедали» все ресурсы, а остальные падали
# в сниппет-фолбэк).
ARTICLE_FETCH_TIMEOUT_SECONDS = settings.bp1_article_fetch_timeout_seconds

# Режим фильтрации релевантности (off/filter/rank) и порог по умолчанию.
RELEVANCE_MODE = getattr(settings, 'bp1_relevance_mode', 'off')
RELEVANCE_THRESHOLD = float(getattr(settings, 'bp1_relevance_threshold', 0.6))

# Включает LLM-обогащение событий структурированными полями.
ENRICHMENT_ENABLED = bool(getattr(settings, 'bp1_enrichment_enabled', False))

# Минимальное количество символов, при котором извлечённый LLM/CSS текст
# считается полным. Если текст короче — вероятна обрезка, и нужна докачка
# хвоста.
MIN_FULL_ARTICLE_TEXT_LENGTH = settings.bp1_min_full_article_text_length

# Максимальное количество итераций докачки обрезанного хвоста статьи.
MAX_TAIL_FETCH_ATTEMPTS = settings.bp1_max_tail_fetch_attempts

# Максимальное количество байт исходного HTML, отдаваемых LLM в одном запросе
# докачки хвоста (смещение по оффсету в конец документа).
TAIL_FETCH_CHUNK_SIZE = settings.bp1_tail_fetch_chunk_size
