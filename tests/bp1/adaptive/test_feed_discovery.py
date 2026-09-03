"""Тесты обнаружения RSS/Atom-фида и sitemap.xml (discovery.py)."""

from src.bp1.adaptive.processing.feed.discovery import (
    discover_feed,
    find_feed_link_in_html,
)

_VALID_RSS = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    '<title>Feed</title>'
    '<item><title>N1</title><link>https://example.com/1</link>'
    '<description>D1</description></item>'
    '</channel></rss>'
)

_VALID_SITEMAP = (
    '<?xml version="1.0"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    '<url><loc>https://example.com/a</loc></url>'
    '</urlset>'
)

_NOT_A_FEED_HTML = '<html><body>404 not found</body></html>'


def _fetch_from(routes: dict[str, str]):
    def fetch(url: str) -> str:
        if url not in routes:
            raise RuntimeError(f'not found: {url}')
        return routes[url]

    return fetch


class TestFindFeedLinkInHtml:
    def test_finds_rss_link(self):
        html = (
            '<html><head>'
            '<link rel="alternate" type="application/rss+xml" '
            'href="/rss.xml">'
            '</head><body></body></html>'
        )
        found = find_feed_link_in_html(html, 'https://example.com')
        assert found == ('https://example.com/rss.xml', 'rss')

    def test_finds_atom_link_with_absolute_href(self):
        html = (
            '<html><head>'
            '<link rel="alternate" type="application/atom+xml" '
            'href="https://example.com/atom.xml">'
            '</head></html>'
        )
        found = find_feed_link_in_html(html, 'https://example.com')
        assert found == ('https://example.com/atom.xml', 'rss')

    def test_ignores_link_without_alternate_rel(self):
        html = (
            '<html><head>'
            '<link rel="stylesheet" type="application/rss+xml" '
            'href="/rss.xml">'
            '</head></html>'
        )
        assert find_feed_link_in_html(html, 'https://example.com') is None

    def test_no_link_returns_none(self):
        html = '<html><head></head><body>no feed here</body></html>'
        assert find_feed_link_in_html(html, 'https://example.com') is None

    def test_empty_html_returns_none(self):
        assert find_feed_link_in_html('', 'https://example.com') is None


class TestDiscoverFeed:
    def test_uses_link_declaration_when_html_given(self):
        html = (
            '<html><head><link rel="alternate" '
            'type="application/rss+xml" href="/custom-feed"></head></html>'
        )
        fetch = _fetch_from({'https://example.com/custom-feed': _VALID_RSS})

        found = discover_feed('https://example.com', html, fetch=fetch)

        assert found is not None
        assert found.url == 'https://example.com/custom-feed'
        assert found.kind == 'rss'
        assert found.raw_body == _VALID_RSS

    def test_falls_back_to_conventional_paths_without_html(self):
        fetch = _fetch_from({'https://example.com/rss': _VALID_RSS})

        found = discover_feed('https://example.com', html=None, fetch=fetch)

        assert found is not None
        assert found.url == 'https://example.com/rss'
        assert found.kind == 'rss'

    def test_source_without_feed_returns_none(self):
        fetch = _fetch_from({})

        assert discover_feed('https://example.com', fetch=fetch) is None

    def test_response_200_but_not_valid_feed_is_rejected(self):
        # Все конвенциональные пути отвечают, но ни один не отдаёт
        # валидный RSS/Atom/sitemap (например, HTML-заглушка 404) —
        # обнаружение SHALL NOT принять такой ответ как успех
        # (specs/bp1/rss-sitemap-collection/spec.md, «Валидация...»).
        fetch = _fetch_from(
            {
                'https://example.com/rss': _NOT_A_FEED_HTML,
                'https://example.com/rss.xml': _NOT_A_FEED_HTML,
                'https://example.com/feed': _NOT_A_FEED_HTML,
                'https://example.com/feed.xml': _NOT_A_FEED_HTML,
                'https://example.com/atom.xml': _NOT_A_FEED_HTML,
                'https://example.com/sitemap.xml': _NOT_A_FEED_HTML,
                'https://example.com/sitemap_index.xml': _NOT_A_FEED_HTML,
            }
        )

        assert discover_feed('https://example.com', fetch=fetch) is None

    def test_finds_sitemap_when_no_rss_available(self):
        fetch = _fetch_from({'https://example.com/sitemap.xml': _VALID_SITEMAP})

        found = discover_feed('https://example.com', fetch=fetch)

        assert found is not None
        assert found.kind == 'sitemap'
        assert found.url == 'https://example.com/sitemap.xml'

    def test_link_candidate_invalid_falls_back_to_conventional_paths(self):
        # <link> указывает на невалидный фид — обнаружение не должно
        # останавливаться на нём, а пробовать конвенциональные пути дальше.
        html = (
            '<html><head><link rel="alternate" '
            'type="application/rss+xml" href="/broken"></head></html>'
        )
        fetch = _fetch_from(
            {
                'https://example.com/broken': _NOT_A_FEED_HTML,
                'https://example.com/rss': _VALID_RSS,
            }
        )

        found = discover_feed('https://example.com', html, fetch=fetch)

        assert found is not None
        assert found.url == 'https://example.com/rss'
