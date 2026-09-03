"""Обнаружение RSS/Atom-фида и ``sitemap.xml`` источника
(BP-1 Adaptive, RSS/sitemap).

Два дешёвых, детерминированных способа, без LLM (design.md D1):

1. Разбор ``<link rel="alternate" type="application/rss+xml"|
   "application/atom+xml">`` в ``<head>`` уже полученного HTML —
   самодекларация сайта, приоритетнее угаданного пути.
2. Проба фиксированного списка конвенциональных путей.

Валидация кандидата — по факту разбора (``parse_rss_entries``/
``parse_sitemap`` дают непустой результат), а не по одному HTTP 200: путь
может отвечать 200 и при этом отдавать HTML-заглушку 404 или пустую
страницу.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .rss import parse_rss_entries
from .sitemap import parse_sitemap

logger = logging.getLogger(__name__)

# Конвенциональные пути в порядке приоритета: (путь, вид).
_CONVENTIONAL_PATHS: tuple[tuple[str, str], ...] = (
    ('/rss', 'rss'),
    ('/rss.xml', 'rss'),
    ('/feed', 'rss'),
    ('/feed.xml', 'rss'),
    ('/atom.xml', 'rss'),
    ('/sitemap.xml', 'sitemap'),
    ('/sitemap_index.xml', 'sitemap'),
)

_LINK_ALTERNATE_TYPES = ('application/rss+xml', 'application/atom+xml')

_FEED_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
)
_DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DiscoveredFeed:
    """Найденный фид/sitemap: адрес, вид и уже скачанное тело ответа.

    ``raw_body`` — тело ответа, полученное во время самой валидации
    кандидата: переиспользуется вызывающим кодом для первого разбора без
    повторного HTTP-запроса сразу после обнаружения.
    """

    url: str
    kind: str  # 'rss' | 'sitemap'
    raw_body: str


def find_feed_link_in_html(html: str, base_url: str) -> tuple[str, str] | None:
    """Ищет ``<link rel="alternate" type="application/rss+xml|atom+xml">``
    в ``<head>`` HTML. Возвращает ``(url, 'rss')`` или ``None``.
    """
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception:
        return None
    for link in soup.find_all('link'):
        rel = link.get('rel')
        rel_values = rel if isinstance(rel, list) else [rel] if rel else []
        if 'alternate' not in [str(r).lower() for r in rel_values]:
            continue
        type_attr = (link.get('type') or '').lower()
        if type_attr in _LINK_ALTERNATE_TYPES:
            href = link.get('href')
            if href:
                return urljoin(base_url, href), 'rss'
    return None


def _sync_http_get(
    url: str, timeout_s: float = _DEFAULT_TIMEOUT_SECONDS
) -> str:
    """Простой синхронный GET — фид/sitemap не требуют RPA-обхода
    (прокси/ротация UA/задержки применяются только к стратегиям,
    эмулирующим браузер против защищённого сайта, см.
    specs/bp1/rpa-network-controls/spec.md, «Область применения ограничена
    RPA-стратегиями») — тот же класс, что ``FastStrategy``/``WAYBACK``.
    """
    req = urllib.request.Request(url, headers={'User-Agent': _FEED_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode('utf-8', errors='replace')


def _validate_candidate(
    fetch: Callable[[str], str], url: str, kind: str
) -> DiscoveredFeed | None:
    try:
        body = fetch(url)
    except Exception as exc:
        logger.debug('Кандидат фида %s недоступен: %s', url, exc)
        return None
    if not body:
        return None
    if kind == 'rss':
        if parse_rss_entries(body):
            return DiscoveredFeed(url=url, kind='rss', raw_body=body)
        return None
    if parse_sitemap(body):
        return DiscoveredFeed(url=url, kind='sitemap', raw_body=body)
    return None


def discover_feed(
    host_url: str,
    html: str | None = None,
    *,
    fetch: Callable[[str], str] | None = None,
) -> DiscoveredFeed | None:
    """Обнаружение фида/sitemap для источника (синхронное ядро).

    ``fetch`` — инжектируемый транспорт (по умолчанию — простой HTTP GET);
    тот же приём, что уже применяет ``SearchUrlProber``
    (``integration/search_probe.py``) для тестируемости без сети.
    """
    fetch = fetch or _sync_http_get

    if html:
        link = find_feed_link_in_html(html, host_url)
        if link is not None:
            found = _validate_candidate(fetch, link[0], link[1])
            if found is not None:
                return found

    for path, kind in _CONVENTIONAL_PATHS:
        url = urljoin(host_url, path)
        found = _validate_candidate(fetch, url, kind)
        if found is not None:
            return found

    return None


async def discover_feed_async(
    host_url: str,
    html: str | None = None,
    *,
    fetch: Callable[[str], str] | None = None,
) -> DiscoveredFeed | None:
    """Асинхронная обёртка: синхронный перебор в отдельном потоке."""
    return await asyncio.to_thread(discover_feed, host_url, html, fetch=fetch)


async def fetch_feed_body_async(
    url: str, *, fetch: Callable[[str], str] | None = None
) -> str:
    """Скачивает тело уже известного (закэшированного) URL фида/sitemap."""
    fetch = fetch or _sync_http_get
    return await asyncio.to_thread(fetch, url)
