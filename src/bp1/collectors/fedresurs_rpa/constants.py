"""Все константы: URL, селекторы, таймауты, пул UA, задержки.

Пул User-Agent и функции случайной задержки перенесены в
``src.bp1.network`` (общие для обоих RPA-контуров BP-1, см.
``openspec/changes/add-rpa-collection-proxying``) и реэкспортируются
здесь для обратной совместимости — вызывающий код (``browser.py``,
``parser.py``, ``config.py``) не меняется.
"""

from pathlib import Path

from src.bp1.network.delay import (
    DEFAULT_DELAY_BETWEEN_REQUESTS,
    HUMAN_DELAY_RANGE,
    get_human_delay,
    get_random_delay,
)
from src.bp1.network.ua_rotation import USER_AGENTS, get_random_user_agent

# Реэкспорт из src.bp1.network — эти имена не используются напрямую в
# этом модуле, но остаются частью его публичного API (см. docstring).
__all__ = [
    'DEFAULT_DELAY_BETWEEN_REQUESTS',
    'HUMAN_DELAY_RANGE',
    'USER_AGENTS',
    'get_human_delay',
    'get_random_delay',
    'get_random_user_agent',
]

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

# Timeouts
DEFAULT_TIMEOUT = 60000  # 60 seconds (QRATOR challenge needs ~25s)
DEFAULT_ELEMENT_TIMEOUT = 10000  # 10 seconds
DEFAULT_RETRY_COUNT = 3

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
