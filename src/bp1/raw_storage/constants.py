"""Константы модуля raw_storage.

Все именованные значения, строки и магические числа собраны здесь
для единого управления конфигурацией модуля.
"""

# ── Пути и файловая система ──────────────────────────────────────────────────
DEFAULT_BASE_PATH = "data/raw"
JSON_INDENT = 2
FILE_EXTENSION = ".json"
JSON_GLOB_PATTERN = "*.json"

# ── Префиксы директорий и файлов ────────────────────────────────────────────
TRIGGER_DIR_PREFIX = "trigger_"
RAW_FILE_PREFIX = "raw_"

# ── Кодировки ────────────────────────────────────────────────────────────────
ENCODING_UTF8 = "utf-8"
ENCODING_ASCII = "ascii"
ENCODING_BASE64 = "base64"

# ── Режимы работы с файлами ─────────────────────────────────────────────────
FILE_MODE_WRITE = "w"
FILE_MODE_READ = "r"

# ── Логирование: длина обрезки чексуммы в логах ──────────────────────────────
CHECKSUM_LOG_LENGTH = 12

# ── JSON-ключи секций в файле ────────────────────────────────────────────────
JSON_KEY_SOURCE = "source"
JSON_KEY_TRIGGER = "trigger"
JSON_KEY_REQUEST = "request"
JSON_KEY_CONTENT = "content"
JSON_KEY_STORAGE = "storage"
JSON_KEY_PROCESSING = "processing"
JSON_KEY_METADATA = "metadata"

# ── JSON-ключи внутри секций ─────────────────────────────────────────────────
JSON_KEY_RAW_ID = "raw_id"
JSON_KEY_CRAWLED_AT = "crawled_at"
JSON_KEY_DATA = "data"
JSON_KEY_CONTENT_TYPE = "content_type"
JSON_KEY_FORMAT = "format"
JSON_KEY_PATH = "path"
JSON_KEY_CHECKSUM = "checksum_sha256"
JSON_KEY_STATUS = "status"
JSON_KEY_CLEANED_AT = "cleaned_at"
JSON_KEY_CATEGORY = "category"
JSON_KEY_ERROR = "error"
JSON_KEY_HTTP_STATUS = "http_status"
JSON_KEY_HEADERS = "headers"
JSON_KEY_TYPE = "type"
JSON_KEY_NAME = "name"
JSON_KEY_URL = "url"
JSON_KEY_ID = "id"
JSON_KEY_KEYWORDS = "keywords"
