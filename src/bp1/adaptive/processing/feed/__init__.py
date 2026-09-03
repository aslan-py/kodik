"""RSS/Atom-фид и sitemap.xml как альтернатива HTML-лестнице для
новостных источников BP-1 (design.md изменения add-rss-sitemap-collection).

Публичный API пакета — то, что использует ``AdaptiveParser``:
- ``discover_feed_async`` — обнаружение фида (конвенциональные пути +
  ``<link rel="alternate">``).
- ``parse_rss_entries`` / ``entries_to_materials`` — RSS/Atom -> материалы.
- ``parse_sitemap`` — sitemap.xml/sitemap_index.xml -> список URL.
- ``annotate_materials`` — разметка материалов по совпадению с конкурентом
  (строковое совпадение, без LLM).
"""

from __future__ import annotations

from .competitor_match import annotate_materials, matches_competitor
from .discovery import (
    DiscoveredFeed,
    discover_feed,
    discover_feed_async,
    fetch_feed_body_async,
    find_feed_link_in_html,
)
from .rss import entries_to_materials, parse_rss_entries
from .sitemap import SitemapUrl, parse_sitemap

__all__ = [
    'DiscoveredFeed',
    'SitemapUrl',
    'annotate_materials',
    'discover_feed',
    'discover_feed_async',
    'entries_to_materials',
    'fetch_feed_body_async',
    'find_feed_link_in_html',
    'matches_competitor',
    'parse_rss_entries',
    'parse_sitemap',
]
