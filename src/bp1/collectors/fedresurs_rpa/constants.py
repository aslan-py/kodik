"""Все константы: URL, селекторы, таймауты, пул UA, задержки."""

import random
from pathlib import Path

BASE_URL = 'https://fedresurs.ru'

# SELECTORS — verified on fedresurs.ru (Angular 15 SPA)
SELECTORS = {
    'combobox': 'combobox',  # getByRole('combobox')
    'options_list_label': 'Options list',  # getByLabel('Options list')
    'category_text': 'Лица',
    'search_input_container': 'el-search-input',
    'search_button_container': 'el-button',
    'results_link_text': 'Вся информация',
    'logo': 'a[href="/"]',
    'loading_indicator': '.loading',
    # Селекторы для извлечения данных из карточки компании
    'company_status': '.label-item-text',
    'company_info_container': '.information-content',
    'company_name': '.company-name, .entity-header',
    'company_inn': '[data-testid="inn"], .inn-value',
    'company_address': '.company-address, .address-value',
    # НОВЫЕ селекторы для расширенного парсинга
    'registration_date': '.info-item-value',  # Для даты регистрации
    'director_block': '.ieb-item',  # Блок с руководителем
    'director_name': '.ieb-name span',  # Имя руководителя
    'director_inn': '.info-item-name:has-text("ИНН") + .info-item-value',
    'director_position': '.info-item-name:has-text("Должность") + .info-item-value',  # noqa: E501
    'director_date': '.info-item-name:has-text("Дата внесения") + .info-item-value',  # noqa: E501
}

# User-Agent Pool (Chromium-based for consistency with stealth)
USER_AGENTS = [
    # Реальные User-Agent строки — разбивка недопустима
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
]

# Timeouts
DEFAULT_TIMEOUT = 60000  # 60 seconds (QRATOR challenge needs ~25s)
DEFAULT_ELEMENT_TIMEOUT = 10000  # 10 seconds
DEFAULT_RETRY_COUNT = 3

# Delays
DEFAULT_DELAY_BETWEEN_REQUESTS = (1.0, 3.0)
HUMAN_DELAY_RANGE = (0.3, 0.5)
TYPING_DELAY_MS = 50

# Viewport
VIEWPORT = {'width': 1920, 'height': 1080}

# QRATOR timing
QRATOR_CHALLENGE_WAIT_MS = 25000
QRATOR_POST_NAVIGATION_WAIT_MS = 3000
QRATOR_LOGO_CLICK_WAIT_MS = 5000

# Длина ИНН (валидация в utils.validate_inn)
INN_LEGAL_ENTITY_LENGTH = 10
INN_INDIVIDUAL_LENGTH = 12


# Путь для сохранения HTML файлов (относительно пакета fedresurs_rpa)
OUTPUT_DIR = str(
    Path(__file__).resolve().parent.parent.parent / 'data' / 'html_pages'
)


def get_random_user_agent() -> str:
    """Вернуть случайный User-Agent из пула."""
    return random.choice(USER_AGENTS)


def get_random_delay() -> float:
    """Вернуть случайную задержку между запросами (1-3 сек)."""
    return random.uniform(*DEFAULT_DELAY_BETWEEN_REQUESTS)


def get_human_delay() -> float:
    """Вернуть случайную задержку, имитирующую поведение человека."""
    return random.uniform(*HUMAN_DELAY_RANGE)
