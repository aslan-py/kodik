"""Переиспользуемый модуль антидетект-стелса для Playwright."""

from .browser_config import apply_stealth, get_context_config, get_launch_args
from .qrator_bypass import bypass_qrator

__all__ = [
    'apply_stealth',
    'bypass_qrator',
    'get_context_config',
    'get_launch_args',
]
