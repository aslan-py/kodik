"""AdaptiveParser — интеллектуальный парсинг с анализом структуры HTML.

Реэкспортирует публичный API пакета (см. ``core.py`` для основной логики,
остальные модули — вынесенные утилиты по зонам ответственности):

- ``constants`` — лимиты и пороги.
- ``url_utils`` — фильтрация служебных/рекламных ссылок, нормализация.
- ``selectors`` — извлечение элементов по CSS-селекторам.
- ``content`` — извлечение и оценка полноты текста статьи.
- ``pagination`` — пагинация выдачи и сборка элементов данных.
- ``core`` — класс ``AdaptiveParser``.
"""

from .constants import (
    ADAPTER_FAIL_THRESHOLD,
    DEFAULT_MAX_NEWS,
    MAX_PAGINATION_PAGES,
    MIN_ARTICLE_TEXT_LENGTH,
    MIN_FULL_ARTICLE_TEXT_LENGTH,
)
from .content import _looks_truncated
from .core import AdaptiveParser
from .pagination import (
    _items_per_page,
    _page_items,
    _pagination_url,
    _parse_items,
)
from .url_utils import _is_ad_redirect_url, _is_noise_url, _to_absolute

__all__ = [
    'ADAPTER_FAIL_THRESHOLD',
    'DEFAULT_MAX_NEWS',
    'MAX_PAGINATION_PAGES',
    'MIN_ARTICLE_TEXT_LENGTH',
    'MIN_FULL_ARTICLE_TEXT_LENGTH',
    'AdaptiveParser',
    '_is_ad_redirect_url',
    '_is_noise_url',
    '_items_per_page',
    '_looks_truncated',
    '_page_items',
    '_pagination_url',
    '_parse_items',
    '_to_absolute',
]
