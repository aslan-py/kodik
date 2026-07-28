from src.bp2.dedup import make_dedup_key, norm

# --- norm ---


def test_norm_lowercases():
    assert norm('Привет') == 'привет'


def test_norm_removes_punctuation():
    assert norm('Бегемот!') == 'бегемот'


def test_norm_collapses_spaces():
    assert norm('один  два   три') == 'один два три'


def test_norm_strips_edges():
    assert norm('  текст  ') == 'текст'


def test_norm_none_returns_empty():
    assert norm(None) == ''


def test_norm_empty_returns_empty():
    assert norm('') == ''


def test_norm_punctuation_and_quotes():
    assert norm('«Бегемот», открыл!') == 'бегемот открыл'


# --- make_dedup_key ---


def test_same_content_same_key():
    k1 = make_dedup_key('Бегемот', 'Открыл склад', '2026-06-25', 'Москва')
    k2 = make_dedup_key('Бегемот', 'Открыл склад', '2026-06-25', 'Москва')
    assert k1 == k2


def test_title_case_insensitive():
    k1 = make_dedup_key('Бегемот', 'Открыл склад', '2026-06-25', 'Москва')
    k2 = make_dedup_key('Бегемот', 'ОТКРЫЛ СКЛАД', '2026-06-25', 'Москва')
    assert k1 == k2


def test_title_punctuation_insensitive():
    k1 = make_dedup_key('Бегемот', 'Открыл склад', '2026-06-25', 'Москва')
    k2 = make_dedup_key('Бегемот', 'Открыл склад!', '2026-06-25', 'Москва')
    assert k1 == k2


def test_different_competitor_different_key():
    k1 = make_dedup_key('Бегемот', 'Открыл склад', '2026-06-25', 'Москва')
    k2 = make_dedup_key('Топ-Сервис', 'Открыл склад', '2026-06-25', 'Москва')
    assert k1 != k2


def test_different_date_different_key():
    k1 = make_dedup_key('Бегемот', 'Открыл склад', '2026-06-25', 'Москва')
    k2 = make_dedup_key('Бегемот', 'Открыл склад', '2026-06-26', 'Москва')
    assert k1 != k2


def test_none_fields_dont_raise():
    key = make_dedup_key(None, None, None, None)
    assert isinstance(key, str) and len(key) == 64


def test_key_is_64_chars_hex():
    key = make_dedup_key('А', 'Б', 'В', 'Г')
    assert len(key) == 64
    assert all(c in '0123456789abcdef' for c in key)
