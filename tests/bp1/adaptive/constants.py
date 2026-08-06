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
QUALITY_REPORTS_COUNT = 5
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
SEARCH_URL = 'https://lenta.ru/search?q=ИИ'
REDIS_CLASSIFICATION_KEY = 'bp1:classification:lenta.ru'

# ---------------------------------------------------------------------------
# test_mcp
# ---------------------------------------------------------------------------
MCP_JSONRPC = '2.0'
MCP_PROTOCOL_VERSION = '2024-11-05'
MCP_SERVER_NAME = 'bp1-adaptive'
MCP_METHOD_INITIALIZE = 'initialize'
MCP_METHOD_TOOLS_LIST = 'tools/list'
MCP_METHOD_TOOLS_CALL = 'tools/call'
MCP_TOOL_CLASSIFY_SOURCE = 'classify_source'
MCP_TOOL_RUN_PARSE = 'run_adaptive_parse'
MCP_TOOL_LIST_STRATEGIES = 'list_strategies'
MCP_ERROR_METHOD_NOT_FOUND = -32601
MCP_ERROR_INTERNAL = -32603

# ---------------------------------------------------------------------------
# test_llm / test_llm_smoke
# ---------------------------------------------------------------------------
ENV_LLM_API_KEY = 'LLM_API_KEY'
ENV_OPENAI_API_KEY = 'OPENAI_API_KEY'
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
