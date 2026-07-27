from datetime import date

from src.bp2.schemas import (
    TITLE_PLACEHOLDER,
    RawEventIn,
    domain_from_url,
    parse_ru_date,
)

# --- parse_ru_date ---


def test_iso_format():
    assert parse_ru_date('2026-06-25') == date(2026, 6, 25)


def test_numeric_format():
    assert parse_ru_date('23.06.2026') == date(2026, 6, 23)


def test_russian_text_format():
    assert parse_ru_date('26 июня 2026') == date(2026, 6, 26)


def test_all_russian_months():
    months = [
        ('января', 1),
        ('февраля', 2),
        ('марта', 3),
        ('апреля', 4),
        ('мая', 5),
        ('июня', 6),
        ('июля', 7),
        ('августа', 8),
        ('сентября', 9),
        ('октября', 10),
        ('ноября', 11),
        ('декабря', 12),
    ]
    for name, num in months:
        result = parse_ru_date(f'1 {name} 2026')
        assert result == date(2026, num, 1), f'Не распознан месяц: {name}'


def test_invalid_string_returns_none():
    assert parse_ru_date('не дата') is None


def test_empty_string_returns_none():
    assert parse_ru_date('') is None


def test_none_returns_none():
    assert parse_ru_date(None) is None


def test_date_object_returned_as_is():
    d = date(2026, 1, 1)
    assert parse_ru_date(d) is d


# --- domain_from_url ---


def test_domain_extracts_from_url():
    assert domain_from_url('https://big-news.ru/article/1') == 'big-news.ru'


def test_www_prefix_stripped():
    assert domain_from_url('https://www.kommersant.ru/doc/1') == 'kommersant.ru'


def test_domain_none_returns_none():
    assert domain_from_url(None) is None


def test_domain_empty_string_returns_none():
    assert domain_from_url('') is None


def test_domain_lowercased():
    assert domain_from_url('https://BIG-NEWS.RU/path') == 'big-news.ru'


# --- RawEventIn ---


def test_empty_title_becomes_placeholder():
    ev = RawEventIn.model_validate({'title': '', 'url': 'https://example.com'})
    assert ev.title == TITLE_PLACEHOLDER


def test_none_title_becomes_placeholder():
    ev = RawEventIn.model_validate(
        {'title': None, 'url': 'https://example.com'}
    )
    assert ev.title == TITLE_PLACEHOLDER


def test_missing_title_becomes_placeholder():
    ev = RawEventIn.model_validate({'url': 'https://example.com'})
    assert ev.title == TITLE_PLACEHOLDER


def test_normal_title_preserved():
    ev = RawEventIn.model_validate({'title': 'Открытие склада'})
    assert ev.title == 'Открытие склада'


def test_published_at_parsed_from_string():
    ev = RawEventIn.model_validate({'published_at': '25.06.2026'})
    assert ev.published_at == date(2026, 6, 25)


def test_media_domain_derived_from_url():
    ev = RawEventIn.model_validate({'url': 'https://www.forbes.ru/1'})
    assert ev.media_domain == 'forbes.ru'


def test_extra_defaults_to_empty_dict():
    ev = RawEventIn.model_validate({})
    assert ev.extra == {}


def test_unknown_fields_ignored():
    ev = RawEventIn.model_validate(
        {'title': 'Тест', 'trigger': 'ключевое слово'}
    )
    assert ev.title == 'Тест'
