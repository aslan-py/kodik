"""Константы для тестов пакета bp1.adaptive.

Содержит вынесенные магические числа и именованные константы, используемые
в тестовых модулях ``kodik/tests/bp1/adaptive``.
"""

# ---------------------------------------------------------------------------
# Общие значения
# ---------------------------------------------------------------------------
EXAMPLE_URL = 'https://example.com'
EXAMPLE_SOURCE_NAME = 'example.com'
DEDUP_KEY_URL = 'url'

MODULE_CRAWL4AI = 'crawl4ai'
MODULE_PLAYWRIGHT = 'playwright.async_api'

# ---------------------------------------------------------------------------
# test_chunking
# ---------------------------------------------------------------------------
HTML_CLEANER_MIN_TEXT_LENGTH = 10
HTML_CLEANER_SHORT_MIN_TEXT_LENGTH = 5

CHUNK_MAX_SIZE_SINGLE = 8000
CHUNK_OVERLAP_SINGLE = 500
CHUNK_MAX_SIZE_MULTI = 100
CHUNK_OVERLAP_MULTI = 20
CHUNK_BLOCKS_COUNT = 20
CHUNK_MAX_SIZE_CHARS = 50
CHUNK_OVERLAP_CHARS = 10
CHUNK_CONTENT_REPEAT = 200
CHUNK_TEST_CONTENT = 'abc'
CHUNK_TEST_CONTENT_SIZE = 3

MERGER_CONFIDENCE_HIGH = 0.9
MERGER_CONFIDENCE_LOW = 0.8
MERGER_CONFIDENCE_AVG = 0.85
MERGER_TOTAL_ITEMS = 4
MERGER_DUPLICATE_COUNT = 1
MERGER_UNIQUE_ITEMS = 3

MERGER_FALLBACK_CONFIDENCE_A = 0.7
MERGER_FALLBACK_CONFIDENCE_B = 0.6

# ---------------------------------------------------------------------------
# test_classifier
# ---------------------------------------------------------------------------
CLASSIFIER_API_NAME = 'api.hh.ru'
CLASSIFIER_API_URL = 'https://api.hh.ru/vacancies'
CLASSIFIER_REGISTRY_NAME = 'fedresurs.ru'
CLASSIFIER_REGISTRY_URL = 'https://fedresurs.ru/entities'
CLASSIFIER_NEWS_NAME = 'lenta.ru'
CLASSIFIER_NEWS_URL = 'https://lenta.ru/news'
CLASSIFIER_SIMPLE_NAME = 'example.com'
CLASSIFIER_SIMPLE_URL = 'https://example.com'

CLASSIFIER_CAPTCHA_HTML = (
    '<html><body><div class="g-recaptcha"></div></body></html>'
)
CLASSIFIER_ANTIBOT_HEADERS = {'Server': 'cloudflare', 'CF-RAY': 'abc123'}
CLASSIFIER_SPA_HTML = '<html><body><div id="app"></div></body></html>'

CLASSIFIER_COMPLEXITY_THRESHOLD = 0.5

# HTML с schema.org разметкой товара (e-commerce).
CLASSIFIER_E_COMMERCE_HTML = (
    '<html><head>'
    '<meta property="og:type" content="product">'
    '</head><body>'
    '<div itemscope itemtype="https://schema.org/Product">'
    '<span class="price">1000</span>'
    '</div>'
    '</body></html>'
)

# HTML с schema.org разметкой вакансии.
CLASSIFIER_JOB_HTML = (
    '<html><body>'
    '<div itemscope itemtype="https://schema.org/JobPosting">'
    '<span class="title">Вакансия</span>'
    '</div>'
    '</body></html>'
)

# HTML с корзиной (e-commerce по CSS).
CLASSIFIER_CART_HTML = (
    '<html><body><div class="shopping-cart">Корзина</div></body></html>'
)

# HTML с React-маркерами.
CLASSIFIER_REACT_HTML = (
    '<html><body><div data-reactroot><div id="app"></div></div></body></html>'
)

# HTML с Vue-маркерами.
CLASSIFIER_VUE_HTML = (
    '<html><body><div data-v-12345 v-if="ok"></div></body></html>'
)

# HTML с Angular-маркерами.
CLASSIFIER_ANGULAR_HTML = '<html><body><div ng-app="app"></div></body></html>'

# HTML с Bootstrap CSS.
CLASSIFIER_BOOTSTRAP_HTML = (
    '<html><head><link href="bootstrap.min.css"></head><body>'
    '<button class="btn-primary">Go</button></body></html>'
)

# HTML с Tailwind CSS.
CLASSIFIER_TAILWIND_HTML = (
    '<html><head><link href="tailwindcss"></head>'
    '<body><div class="hover:bg-red"></div></body></html>'
)

# HTML с Яндекс.Метрикой.
CLASSIFIER_METRIKA_HTML = (
    '<html><head><script>(function(m,t,e,r,s){yandex_metrika}'
    ')</script></head></html>'
)

# HTML-страница с вакансиями для extended-классификации.
CLASSIFIER_JOB_PAGE_HTML = (
    '<html><body>'
    '<div class="vacancy">'
    '<h2 class="title">Разработчик</h2>'
    '<span class="salary">200000</span>'
    '</div>'
    '<div class="pagination"><a href="?page=2">Далее</a></div>'
    '</body></html>'
)

# ---------------------------------------------------------------------------
# test_engines
# ---------------------------------------------------------------------------
ENGINE_FAKE_ERROR = 'crawl4ai unavailable'
ENGINE_PLAYWRIGHT_ERROR = 'playwright unavailable'
ENGINE_HITL_REQUEST_ID = 'test'
ENGINE_HITL_ERROR = 'challenge requires human interaction'
ENGINE_HITL_RESOLVED_CONTENT_REPEAT = 30
ENGINE_HITL_SESSION_COOKIE = 'abc'

# ---------------------------------------------------------------------------
# test_hitl
# ---------------------------------------------------------------------------
HITL_PROFILES_DIR = 'profiles'
HITL_REQUESTS_DIR = 'requests'
HITL_CACHE_DIR = 'cache'
HITL_JSON_GLOB = '*.json'
HITL_REQUEST_ID_1 = 'test-request-1'
HITL_REQUEST_ID_2 = 'test-request-2'
HITL_REQUEST_ID_3 = 'test-request-3'
HITL_STATUS_PENDING = 'pending'
HITL_STATUS_RESOLVED = 'resolved'
HITL_STATUS_NOT_FOUND = 'not_found'
HITL_NONEXISTENT_ID = 'nonexistent'

# ---------------------------------------------------------------------------
# test_integration / test_parser
# ---------------------------------------------------------------------------
COMPETITOR = 'ООО АРХИТЕХ'
TRIGGER = 'ИИ'
NEWS_TITLE = 'Новость про ИИ'
NEWS_LINK = 'https://example.com/news/1'
SEARCH_TASK_ID = 1
ADAPTER_CONFIDENCE = 0.9
PARSER_TYPE_ADAPTIVE = 'adaptive'
TITLE_SELECTOR = 'a'
TITLE_FIELD = 'title'

# ---------------------------------------------------------------------------
# test_parser
# ---------------------------------------------------------------------------
PARSER_STATUS_OK = 'ok'
PARSER_STATUS_ERROR = 'error'
NETWORK_ERROR = 'network error'
NEWS_TITLE_2 = 'Новость про нейросети'
NEWS_LINK_2 = 'https://example.com/news/2'
SELECTOR_CONTAINER = 'div.item'
SELECTOR_TITLE = 'a.title'
SELECTOR_URL = 'a.title'
SELECTOR_DATE = 'span.date'
EXAMPLE_ITEM_URL_1 = 'https://example.com/1'
EXAMPLE_ITEM_URL_2 = 'https://example.com/2'
DATE_1 = '01.01.2026'
DATE_2 = '02.01.2026'
NEWS_1 = 'Новость 1'
NEWS_2 = 'Новость 2'
TEXT_1 = 'Текст новости 1'
TEXT_2 = 'Текст новости 2'
REGION_1 = 'Москва'
REGION_2 = 'СПб'

# ---------------------------------------------------------------------------
# test_quality
# ---------------------------------------------------------------------------
QUALITY_EXPECTED_COUNT = 2
# SCHEMA/TYPES/BUSINESS/VOLUME/CONSISTENCY/RELEVANCE (change
# verify-search-probe-relevance добавила RELEVANCE как 6-й уровень).
QUALITY_REPORTS_COUNT = 6
QUALITY_VOLUME_CURRENT_LOW = 5
QUALITY_VOLUME_CURRENT_OK = 9
QUALITY_VOLUME_EXPECTED = 10
QUALITY_MIN_TEXT_LENGTH = 10
QUALITY_JSON_GLOB = '*.json'
QUALITY_ERROR_MISSING_TITLE = 'missing required field "title"'

# ---------------------------------------------------------------------------
# test_source_registration
# ---------------------------------------------------------------------------
SRC_LENTA_WWW = 'https://www.lenta.ru/news/1'
SRC_LENTA_NORMALIZED = 'https://lenta.ru/'
SRC_LENTA_HOST = 'lenta.ru'
SRC_LENTA_NEWS = 'https://www.lenta.ru/news'
SRC_LENTA_UPPER = 'https://LENTA.RU'
SRC_API_HH = 'https://api.hh.ru/'
SRC_API_HH_HOST = 'api.hh.ru'
SRC_FEDRESURS_PORT = 'http://fedresurs.ru:8080/x'
SRC_FEDRESURS_HOST = 'fedresurs.ru'
SRC_INVALID_REF = 'не ссылка'
SRC_EMPTY = ''
SRC_WHITESPACE = '   '
SEARCH_QUERY = 'ИИ'
# Кодированный URL поиска: query-параметр percent-кодируется (quote_plus),
# кириллица ИИ -> %D0%98%D0%98.
SEARCH_URL = 'https://lenta.ru/search?q=%D0%98%D0%98'
REDIS_CLASSIFICATION_KEY = 'bp1:classification:lenta.ru'

# --- test_register_creates_source / test_register_is_idempotent ---
# Эти два теста реально пишут в БД через фикстуру `session` (rollback
# после теста, без изоляции от УЖЕ закоммиченных строк). БД тестов — та
# же dev-БД (settings.database_url), где lenta.ru зарегистрирован
# по-настоящему (реальный Source с реальными SearchTask), поэтому
# SRC_LENTA_* здесь использовать нельзя — коллизия по уникальному
# Source.name ломает created=True/False. Домен на TLD .invalid
# (зарезервирован RFC 2606 для тестов) гарантированно не столкнётся ни с
# одной настоящей регистрацией; подстрока "news" сохраняет классификацию
# SourceClassifier как SourceType.NEWS.
SRC_TEST_NEWS_URL = 'https://www.test-news-source.invalid/news'
SRC_TEST_NEWS_NORMALIZED = 'https://test-news-source.invalid/'
SRC_TEST_NEWS_HOST = 'test-news-source.invalid'
TEST_NEWS_REDIS_CLASSIFICATION_KEY = (
    'bp1:classification:test-news-source.invalid'
)

# --- test_source_registration: SearchParamResolver / URL-шаблоны ---
# ИНН конкурента (10 цифр — юридическое лицо).
COMPETITOR_INN = '9718283930'
# Название конкурента для не-госсайтов (поиск по competitor.name).
SEARCH_URL_HH_QUERY = 'ООО АРХИТЕХ ИИ'
# hh.ru ищет по названию без кавычек: text=ООО АРХИТЕХ ИИ.
# quote_plus кодирует пробелы как '+'.
SEARCH_URL_HH = (
    'https://hh.ru/search/vacancy?text=%D0%9E%D0%9E%D0%9E+'
    '%D0%90%D0%A0%D0%A5%D0%98%D0%A2%D0%95%D0%A5+%D0%98%D0%98'
)
SEARCH_URL_FEDRESURS_INN = 'https://fedresurs.ru/search?q=9718283930'
SRC_HH_HOST = 'hh.ru'
SRC_ZH = 'zakupki.gov.ru'

# ---------------------------------------------------------------------------
# test_llm / test_llm_smoke
# ---------------------------------------------------------------------------
TEST_API_KEY = 'sk-test'
MODULE_OPENAI = 'openai'
LLM_CHUNK_MAX_SIZE = 2000
LLM_CHUNK_OVERLAP = 200
LLM_ITEM_REPEAT = 200
LLM_TEMPERATURE = 0.0
LLM_CONFIDENCE_HIGH = 0.9
LLM_CONFIDENCE_MEDIUM = 0.8
LLM_CONFIDENCE_LOW = 0.7
LLM_DEFAULT_CONFIDENCE = 0.5
RECOMMENDATION_NO_LLM = 'no_llm'
RECOMMENDATION_IMPROVE = 'improve_selectors'
SCHEMA_TYPE_STRING = 'string'
FAKE_LLM_ERROR = 'llm unavailable'
HTML_EMPTY = '<html></html>'
HTML_WITH_LINK = '<html><body><a href="/1">Новость</a></body></html>'
SELECTOR_URL_VALUE = 'a[href]'
SELECTOR_TITLE_VALUE = 'h2'
CONTAINER_SELECTOR_VALUE = 'div.item'
SMOKE_COMPETITOR = 'ООО "Архитект ИИ"'
EXPECTED_FIELDS_SMOKE: list[str] = []  # expected_fields = ''
ENCODING_UTF8 = 'utf-8'
ENCODING_ERRORS_REPLACE = 'replace'
HTML_GLOB = '*.html'
SOURCE_TYPE_VALUES = {'news', 'registry', 'api', 'spa', 'unknown'}

# ---------------------------------------------------------------------------
# test_orchestrator
# ---------------------------------------------------------------------------
ORCH_ERROR = 'boom'
ORCH_CONTENT = '<html>content</html>'
ORCH_CONTENT_LENGTH = 500
SNAPSHOT_URL = 'http://web.archive.org/web/2026/snapshot'
SNAPSHOT_API_JSON = (
    '{"archived_snapshots": {"closest": '
    '{"url": "http://web.archive.org/web/2026/snapshot"}}}'
)
