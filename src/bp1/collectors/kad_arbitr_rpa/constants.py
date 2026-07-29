# === URL ===
BASE_URL = 'https://kad.arbitr.ru/'

# === Таймауты и задержки ===
DEFAULT_TIMEOUT_MS = 30000
DEFAULT_RETRY_COUNT = 3
DEFAULT_DELAY_BETWEEN_REQUESTS_SEC = 2.0
RANDOM_DELAY_RANGE_SEC = (1.0, 3.0)
HUMAN_DELAY_RANGE_SEC = (0.3, 0.5)
MS_PER_SECOND = 1000

# === Браузер ===
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080
VIEWPORT = {'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT}
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
]

# === CSS-селекторы ===
SELECTORS = {
    # Поле ввода "Участник дела" — это textarea с классом g-ph
    'participant_input': "textarea.g-ph[placeholder*='название']",
    # Кнопка "Найти"
    'search_button': "button[alt='Найти']",
    # Контейнер результатов
    'results_container': '#b-cases tbody tr',
    # Индикатор загрузки
    'loading_indicator': '.b-loading',
}

# === User-Agent пул ===
USER_AGENTS = [
    # Реальные User-Agent строки — разбивка недопустима
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',  # noqa: E501
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',  # noqa: E501
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',  # noqa: E501
    'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',  # noqa: E501
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',  # noqa: E501
]

# === Файлы ===
DEFAULT_OUTPUT_DIR = './parsed_pages'
FILE_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'
FILE_NAME_PREFIX = 'kad_inn_'
FILE_EXTENSION = '.html'
REQUEST_ID_LENGTH = 12

# === Логирование ===
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'
UA_LOG_TRUNCATE = 50
