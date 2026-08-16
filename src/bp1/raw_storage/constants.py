"""Константы модуля raw_storage.

Все именованные значения, строки и магические числа собраны здесь
для единого управления конфигурацией модуля.
"""

from core.config import settings

# ── Пути и файловая система ──────────────────────────────────────────────────
# Единый источник истины — settings.bp1_raw_dir (настраивается через
# BP1_RAW_DIR/BP1_DATA_ROOT в .env, см. README.md). Раньше путь строился
# отдельно через ``Path(__file__).resolve() / 'src' / 'data' / 'raw'`` —
# ``Path(__file__).resolve()`` указывает на сам файл constants.py (не на
# директорию пакета), поэтому итоговый путь не существовал ни при каком
# значении рабочей директории процесса.
DEFAULT_BASE_PATH_RAW = OUTPUT_DIR = settings.bp1_raw_dir
JSON_INDENT = 2
FILE_EXTENSION = '.json'
JSON_GLOB_PATTERN = '*.json'

# ── Префиксы директорий и файлов ────────────────────────────────────────────
TRIGGER_DIR_PREFIX = 'trigger_'
RAW_FILE_PREFIX = 'raw_'

# ── Кодировки ────────────────────────────────────────────────────────────────
ENCODING_UTF8 = 'utf-8'
ENCODING_ASCII = 'ascii'
ENCODING_BASE64 = 'base64'

# ── Режимы работы с файлами ─────────────────────────────────────────────────
FILE_MODE_WRITE = 'w'
FILE_MODE_READ = 'r'

# ── Логирование: длина обрезки чексуммы в логах ──────────────────────────────
CHECKSUM_LOG_LENGTH = 12

# ── JSON-ключи корневой структуры JSONB-файла ────────────────────────────────
JSON_KEY_META = 'meta'
JSON_KEY_ITEMS = 'items'

# ── JSON-ключи секции meta ───────────────────────────────────────────────────
JSON_KEY_SEARCH_TASK_ID = 'search_task_id'
JSON_KEY_SOURCE = 'source'
JSON_KEY_COMPETITOR = 'competitor'
JSON_KEY_TRIGGER = 'trigger'
JSON_KEY_SOURCE_REQUEST_URL = 'source_request_url'
JSON_KEY_FETCHED_AT = 'fetched_at'
JSON_KEY_STATUS = 'status'

# ── JSON-ключи секции items ──────────────────────────────────────────────────
JSON_KEY_URL = 'url'
JSON_KEY_TITLE = 'title'
JSON_KEY_TEXT = 'text'
JSON_KEY_PUBLISHED_AT = 'published_at'
JSON_KEY_REGION = 'region'
JSON_KEY_MEDIA_NAME = 'media_name'
JSON_KEY_EXTRA = 'extra'
