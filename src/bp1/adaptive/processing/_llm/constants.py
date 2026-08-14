"""Константы и параметры по умолчанию для LLM-слоя (BP-1 Adaptive).

Содержит вынесенные магические числа, лимиты, параметры чанкирования и
настройки промптов. Логика вызовов — в соседних модулях пакета.
"""

# Поля по умолчанию для анализа структуры.
DEFAULT_FIELDS = [
    'title',
    'text',
    'published_at',
    'region',
    'url',
    'media_name',
]

# Параметры чанкирования по умолчанию.
DEFAULT_MAX_CHUNK_SIZE = 8000
DEFAULT_OVERLAP_SIZE = 500
DEFAULT_MAX_CHUNKS = 10
DEFAULT_PARALLEL_WORKERS = 5

# Ограничение HTML, передаваемого в промпт (символов).
HTML_SNIPPET_SIZE = 12000

# Лимиты токенов на задачу.
CLASSIFY_MAX_TOKENS = 2048
ANALYZE_MAX_TOKENS = 4096

# Температура для детерминированных задач извлечения.
TEMPERATURE_EXTRACTION = 0.0
# Температура для генеративных задач агента (анализ результата).
TEMPERATURE_GENERATIVE = 0.2

# Скоринг релевантности (Фича 1).
RELEVANCE_MAX_TOKENS = 2048
TEMPERATURE_RELEVANCE = 0.0
DEFAULT_RELEVANCE_THRESHOLD = 0.6
# Максимум элементов в одном LLM-запросе скоринга релевантности (Шаг 14
# плана рефакторинга, N7). Весь список одним запросом рисковал упереться
# в RELEVANCE_MAX_TOKENS при росте числа элементов — ответ обрезался,
# parse_json тихо отдавал {}, и на эвристику откатывался весь список, а
# не только "лишние" элементы. 15 — по ~130 токенов ответа на элемент
# (index/score/relevant) укладывается в RELEVANCE_MAX_TOKENS с запасом.
RELEVANCE_BATCH_SIZE = 15

# Обогащение события (Фича 3).
ENRICHMENT_MAX_TOKENS = 2048
TEMPERATURE_ENRICHMENT = 0.0

# Настройки сетевого слоя (retry-логика).
DEFAULT_TIMEOUT_S = 120
DEFAULT_MAX_RETRIES = 3
RETRY_BASE_DELAY_S = 1.0
RETRY_MAX_DELAY_S = 8.0

# Значения fallback по умолчанию.
FALLBACK_CONFIDENCE = 0.5
DEFAULT_SITE_CONFIDENCE = 0.7
UNKNOWN_SITE_CONFIDENCE = 0.4
