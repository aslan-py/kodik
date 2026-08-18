"""Общий пул User-Agent для RPA-стратегий сбора BP-1.

Перенесено из ``collectors/fedresurs_rpa/constants.py`` (Шаг 2 плана
изменения ``add-rpa-collection-proxying``) — тот же пул теперь общий для
классического контура (``fedresurs_rpa``) и адаптивного (``adaptive/``),
а не независимо задублирован в каждом.
"""

from __future__ import annotations

import random

# Пул User-Agent (Chromium-based — для консистентности со stealth-слоем).
USER_AGENTS = [
    # Реальные User-Agent строки — разбивка недопустима
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',  # noqa: E501
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',  # noqa: E501
]


def get_random_user_agent() -> str:
    """Вернуть случайный User-Agent из общего пула."""
    return random.choice(USER_AGENTS)
