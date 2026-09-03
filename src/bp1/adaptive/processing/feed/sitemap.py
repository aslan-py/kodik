"""``sitemap.xml``/``sitemap_index.xml`` -> список URL-кандидатов
(BP-1 Adaptive, RSS/sitemap).

В отличие от RSS/Atom, sitemap не несёт заголовка/текста/даты — только
список URL (design.md D3). Разбор — стандартная библиотека
(``xml.etree.ElementTree``), без новой зависимости: формат простой, а
namespace sitemap (``http://www.sitemaps.org/schemas/sitemap/0.9``)
снимается сравнением локального имени тега, без привязки к конкретному
URI namespace (некоторые генераторы sitemap опускают namespace вовсе).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import NamedTuple


class SitemapUrl(NamedTuple):
    """Одна запись sitemap: URL и дата последнего изменения (если есть)."""

    url: str
    lastmod: str | None


def _local_name(tag: str) -> str:
    """Имя тега без namespace-префикса (``{ns}url`` -> ``url``)."""
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def parse_sitemap(raw_body: str) -> list[SitemapUrl]:
    """Разбирает ``sitemap.xml`` (``<urlset>``) или ``sitemap_index.xml``
    (``<sitemapindex>``, ссылки на вложенные sitemap-файлы).

    Невалидный XML или неизвестный корневой тег — пустой список, не
    исключение: вызывающий код трактует это как «использовать нечего»,
    так же как пустой список записей RSS/Atom (``parse_rss_entries``).

    Для ``sitemap_index`` возвращает URL самих вложенных sitemap-файлов
    (не URL статей) — рекурсивный разбор вложенности выполняет вызывающий
    код при необходимости.
    """
    if not raw_body:
        return []
    try:
        root = ET.fromstring(raw_body)
    except ET.ParseError:
        return []

    root_tag = _local_name(root.tag)
    if root_tag == 'urlset':
        return _parse_entries(root, 'url')
    if root_tag == 'sitemapindex':
        return _parse_entries(root, 'sitemap')
    return []


def _parse_entries(root: ET.Element, entry_tag: str) -> list[SitemapUrl]:
    entries: list[SitemapUrl] = []
    for node in root:
        if _local_name(node.tag) != entry_tag:
            continue
        loc: str | None = None
        lastmod: str | None = None
        for child in node:
            name = _local_name(child.tag)
            if name == 'loc' and child.text:
                loc = child.text.strip()
            elif name == 'lastmod' and child.text:
                lastmod = child.text.strip()
        if loc:
            entries.append(SitemapUrl(url=loc, lastmod=lastmod))
    return entries
