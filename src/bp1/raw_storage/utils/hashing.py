"""Утилиты для хеширования контента.

Функции:
- compute_sha256 — низкоуровневый SHA-256 от байтов
- compute_content_hash — высокоуровневый: очищает HTML от динамических
  атрибутов (Angular _nghost-*, _ngcontent-*) и вычисляет хеш
"""

from __future__ import annotations

import hashlib
import re

# Паттерны для удаления динамических данных из HTML перед хешированием.
# Эти данные генерируются фреймворками (Angular) или сервером при каждом
# рендеринге и меняются от запроса к запросу, даже если содержимое
# страницы не изменилось.

# 1. Angular-атрибуты: _nghost-oed-c33, _ngcontent-oed-c33 и т.д.
#    В HTML: <tag _nghost-xxx-c33>, в CSS: [_nghost-xxx-c33]
_ANGULAR_ATTR_RE = re.compile(
    r'(?:\[|(?<=\s))_nghost-\w+-\w+\]?'
    r'|'
    r'(?:\[|(?<=\s))_ngcontent-\w+-\w+\]?'
)

# 2. Angular-имена в CSS-анимациях: _ngcontent-oed-c33_
_ANGULAR_ANIM_RE = re.compile(r'_ngcontent-\w+-\w+_')


# 3. CSRF/сессионные токены в autocomplete (уникальные ID сессии браузера)
#    Пример: autocomplete="aa1a2dc9b52d"
_AUTOCOMPLETE_RE = re.compile(r'autocomplete="[a-z0-9]{10,}"')


def compute_sha256(data: bytes) -> str:
    """Вычислить SHA-256 хеш от байтов."""
    return hashlib.sha256(data).hexdigest()


def compute_content_hash(html_content: str) -> str:
    """Вычислить SHA-256 хеш HTML-контента, исключив изменяемые данные.

    Перед вычислением хеша из HTML удаляются динамические данные:
    - Angular-атрибуты (_nghost-*, _ngcontent-*) в HTML и CSS
    - Angular-имена в CSS-анимациях (_ngcontent-*-*_)
    - CSRF/сессионные токены (autocomplete="...")

    Эти данные генерируются фреймворками при каждом рендеринге и
    меняются от запроса к запросу, не влияя на смысловое содержимое.

    Args:
        html_content: Исходный HTML-код страницы.

    Returns:
        SHA-256 хеш от очищенного HTML.
    """
    cleaned = _ANGULAR_ATTR_RE.sub('', html_content)
    cleaned = _ANGULAR_ANIM_RE.sub('_ngcontent-_', cleaned)
    cleaned = _AUTOCOMPLETE_RE.sub('autocomplete=""', cleaned)
    return compute_sha256(cleaned.encode('utf-8'))
