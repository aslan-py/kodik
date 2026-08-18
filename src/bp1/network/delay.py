"""Случайные задержки между действиями RPA-стратегий сбора BP-1.

Перенесено из ``collectors/fedresurs_rpa/constants.py`` (Шаг 2 плана
изменения ``add-rpa-collection-proxying``) — общее для обоих RPA-контуров.
Для паузы МЕЖДУ ЗАПРОСАМИ К ОДНОМУ ХОСТУ (новое требование ТЗ для
``adaptive/``) см. ``network/throttle.py`` — это разные механизмы:
здесь — случайная имитация человеческого поведения внутри одного
сценария, там — гарантированный минимальный интервал между запросами.
"""

from __future__ import annotations

import random

# Задержка между повторными запросами (ретраи), секунды.
DEFAULT_DELAY_BETWEEN_REQUESTS = (1.0, 3.0)
# Задержка, имитирующая паузу человека между действиями, секунды.
HUMAN_DELAY_RANGE = (0.3, 0.5)


def get_random_delay() -> float:
    """Вернуть случайную задержку между повторными запросами (1-3 сек)."""
    return random.uniform(*DEFAULT_DELAY_BETWEEN_REQUESTS)


def get_human_delay() -> float:
    """Вернуть случайную задержку, имитирующую поведение человека."""
    return random.uniform(*HUMAN_DELAY_RANGE)
