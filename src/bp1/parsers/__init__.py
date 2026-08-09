"""
Адаптеры парсеров для различных источников данных.
Каждый адаптер реализует интерфейс BaseParser.
"""

from ..adaptive import AdaptiveBridgeParser
from ..base_parser import ParserFactory
from .fedresurs_adapter import FedresursAdapter

# Регистрируем парсеры в фабрике.
# В фабрике остаётся только реальный RPA-адаптер fedresurs.ru. Для всех
# остальных источников (fips.ru, news.google.com, kad.arbitr.ru,
# kodik.ru/forum, nic.ru, dev.vk.com, zakupki.gov.ru, api.hh.ru и т.д.)
# используются НЕ заглушки, а универсальный адаптивный парсер
# (AdaptiveBridgeParser): он классифицирует источник и применяет стратегии
# обхода (FAST → CRAWL4AI → BROWSER → WAYBACK → STEALTH → HITL) и
# интеллектуальное извлечение данных через LLM/эвристику.
ParserFactory.register('https://fedresurs.ru/', FedresursAdapter)

# Универсальный адаптивный парсер (для любых источников)
ParserFactory.register('adaptive', AdaptiveBridgeParser)

__all__ = [
    'AdaptiveBridgeParser',
    'FedresursAdapter',
    'ParserFactory',
]
