"""Тесты разбора sitemap.xml/sitemap_index.xml (sitemap.py)."""

from src.bp1.adaptive.processing.feed.sitemap import parse_sitemap

_FLAT_SITEMAP = (
    '<?xml version="1.0"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    '<url><loc>https://example.com/a</loc><lastmod>2026-08-01</lastmod></url>'
    '<url><loc>https://example.com/b</loc></url>'
    '</urlset>'
)

_SITEMAP_INDEX = (
    '<?xml version="1.0"?>'
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    '<sitemap><loc>https://example.com/sitemap-1.xml</loc>'
    '<lastmod>2026-08-01</lastmod></sitemap>'
    '<sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>'
    '</sitemapindex>'
)


class TestParseSitemap:
    def test_flat_sitemap_returns_urls_with_lastmod(self):
        entries = parse_sitemap(_FLAT_SITEMAP)

        assert len(entries) == 2
        assert entries[0].url == 'https://example.com/a'
        assert entries[0].lastmod == '2026-08-01'
        assert entries[1].url == 'https://example.com/b'
        assert entries[1].lastmod is None

    def test_sitemap_index_returns_nested_sitemap_urls(self):
        entries = parse_sitemap(_SITEMAP_INDEX)

        assert len(entries) == 2
        assert entries[0].url == 'https://example.com/sitemap-1.xml'
        assert entries[1].url == 'https://example.com/sitemap-2.xml'

    def test_invalid_xml_returns_empty(self):
        assert parse_sitemap('not xml') == []

    def test_unknown_root_tag_returns_empty(self):
        assert parse_sitemap('<foo><bar/></foo>') == []

    def test_empty_body_returns_empty(self):
        assert parse_sitemap('') == []
