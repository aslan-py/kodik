"""Константы и параметры по умолчанию для LLM-слоя (BP-1 Adaptive).

Содержит вынесенные магические числа, лимиты, параметры чанкирования и
настройки промптов. Логика вызовов — в соседних модулях пакета.
"""

from core.config import settings

# Поля по умолчанию для анализа структуры.
DEFAULT_FIELDS = [
    'title',
    'text',
    'published_at',
    'region',
    'url',
    'media_name',
]

# Параметры чанкирования по умолчанию. Размер чанка и их максимальное
# число вынесены в settings (bp1_llm_max_chunk_size/bp1_llm_max_chunks) —
# эксплуатационные ручки, влияющие на потолок длины статьи, которую можно
# извлечь через LLM (см. adaptive/processing/llm.py::_llm_extract_chunked).
DEFAULT_MAX_CHUNK_SIZE = settings.bp1_llm_max_chunk_size
DEFAULT_OVERLAP_SIZE = 500
DEFAULT_MAX_CHUNKS = settings.bp1_llm_max_chunks
DEFAULT_PARALLEL_WORKERS = 5

# Ограничение HTML/текста, передаваемого в промпт (символов). Используется
# для классификации сайта — не влияет на извлечение самого текста статьи
# (ARTICLE_TEXT_PROMPT не использует эту константу вовсе).
HTML_SNIPPET_SIZE = settings.bp1_enrichment_snippet_size

# Лимиты токенов на задачу.
CLASSIFY_MAX_TOKENS = 2048
ANALYZE_MAX_TOKENS = 4096

# Температура для детерминированных задач извлечения.
TEMPERATURE_EXTRACTION = 0.0
# Температура для генеративных задач агента (анализ результата).
TEMPERATURE_GENERATIVE = 0.2

# Настройки сетевого слоя (retry-логика).
DEFAULT_TIMEOUT_S = 120
DEFAULT_MAX_RETRIES = 3
RETRY_BASE_DELAY_S = 1.0
RETRY_MAX_DELAY_S = 8.0

# Значения fallback по умолчанию.
FALLBACK_CONFIDENCE = 0.5
DEFAULT_SITE_CONFIDENCE = 0.7
UNKNOWN_SITE_CONFIDENCE = 0.4
