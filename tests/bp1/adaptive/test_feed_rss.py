"""Тесты сопоставления RSS/Atom -> материалы сбора (rss.py)."""

from src.bp1.adaptive.processing.feed.rss import (
    entries_to_materials,
    parse_rss_entries,
)

_RSS_FULL = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    '<title>Лента</title>'
    '<item>'
    '<title>Новость про ИИ</title>'
    '<link>https://example.com/news/1</link>'
    '<description>Текст новости</description>'
    '</item>'
    '</channel></rss>'
)

_RSS_NO_DESCRIPTION = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    '<item><title>Без описания</title>'
    '<link>https://example.com/news/2</link></item>'
    '</channel></rss>'
)

_RSS_NO_LINK = (
    '<?xml version="1.0"?><rss version="2.0"><channel>'
    '<item><title>Без ссылки</title></item>'
    '</channel></rss>'
)

_ATOM_FULL = (
    '<?xml version="1.0"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom">'
    '<title>Atom feed</title>'
    '<entry>'
    '<title>Atom-новость</title>'
    '<link href="https://example.com/atom/1"/>'
    '<summary>Atom-текст</summary>'
    '</entry>'
    '</feed>'
)

_INVALID_XML = 'not xml at all'


class TestParseRssEntries:
    def test_parses_valid_rss(self):
        entries = parse_rss_entries(_RSS_FULL)
        assert len(entries) == 1
        assert entries[0].title == 'Новость про ИИ'

    def test_parses_valid_atom(self):
        entries = parse_rss_entries(_ATOM_FULL)
        assert len(entries) == 1
        assert entries[0].title == 'Atom-новость'

    def test_invalid_xml_returns_empty(self):
        assert parse_rss_entries(_INVALID_XML) == []

    def test_empty_body_returns_empty(self):
        assert parse_rss_entries('') == []


class TestEntriesToMaterials:
    def test_full_entry_mapped(self):
        materials = entries_to_materials(parse_rss_entries(_RSS_FULL))

        assert len(materials) == 1
        material = materials[0]
        assert material['ex_title'] == 'Новость про ИИ'
        assert material['ex_url'] == 'https://example.com/news/1'
        assert material['ex_text'] == 'Текст новости'
        assert material['ex_method'] == 'rss'
        assert material['ex_text_possibly_incomplete'] is False

    def test_entry_without_description_falls_back_to_title(self):
        materials = entries_to_materials(parse_rss_entries(_RSS_NO_DESCRIPTION))

        assert len(materials) == 1
        material = materials[0]
        assert material['ex_text'] == 'Без описания'
        assert material['ex_text_possibly_incomplete'] is True

    def test_entry_without_link_is_skipped(self):
        materials = entries_to_materials(parse_rss_entries(_RSS_NO_LINK))

        assert materials == []

    def test_mixed_rss_and_atom_sources_both_normalized(self):
        rss_materials = entries_to_materials(parse_rss_entries(_RSS_FULL))
        atom_materials = entries_to_materials(parse_rss_entries(_ATOM_FULL))

        assert rss_materials[0]['ex_method'] == 'rss'
        assert atom_materials[0]['ex_method'] == 'rss'
        assert rss_materials[0]['ex_url'] != atom_materials[0]['ex_url']
