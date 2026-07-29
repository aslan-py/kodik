"""Утилиты для хеширования контента."""

from __future__ import annotations

import hashlib


def compute_sha256(data: bytes) -> str:
    """Вычислить SHA-256 хеш от байтов."""
    return hashlib.sha256(data).hexdigest()
