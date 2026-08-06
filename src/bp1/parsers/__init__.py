"""
Адаптеры парсеров для различных источников данных.
Каждый адаптер реализует интерфейс BaseParser.
"""

from ..adaptive import AdaptiveBridgeParser
from ..base_parser import ParserFactory
from .fedresurs_adapter import FedresursAdapter
from .fips_adapter import FipsAdapter
from .google_news_adapter import GoogleNewsAdapter
from .hh_adapter import HHAdapter
from .kad_arbitr_adapter import KadArbitrAdapter
from .kodik_forum_adapter import KodikForumAdapter
from .nic_ru_adapter import NicRuAdapter
from .vk_adapter import VKAdapter
from .zakupki_adapter import ZakupkiAdapter

# Регистрируем парсеры в фабрике
ParserFactory.register('https://fedresurs.ru/', FedresursAdapter)
ParserFactory.register('https://www.fips.ru/', FipsAdapter)
ParserFactory.register('https://news.google.com/', GoogleNewsAdapter)
ParserFactory.register('https://api.hh.ru/', HHAdapter)
ParserFactory.register('https://kad.arbitr.ru/', KadArbitrAdapter)
ParserFactory.register('https://kodik.ru/forum', KodikForumAdapter)
ParserFactory.register('https://www.nic.ru/', NicRuAdapter)
ParserFactory.register('https://dev.vk.com/', VKAdapter)
ParserFactory.register('https://zakupki.gov.ru/', ZakupkiAdapter)

# Универсальный адаптивный парсер (для любых источников)
ParserFactory.register('adaptive', AdaptiveBridgeParser)

__all__ = [
    'AdaptiveBridgeParser',
    'FedresursAdapter',
    'FipsAdapter',
    'GoogleNewsAdapter',
    'HHAdapter',
    'KadArbitrAdapter',
    'KodikForumAdapter',
    'NicRuAdapter',
    'ParserFactory',
    'VKAdapter',
    'ZakupkiAdapter',
]
