from src.bp2.pipeline import clean_text


def test_none_returns_none():
    assert clean_text(None) is None


def test_empty_string_returns_none():
    assert clean_text('') is None


def test_whitespace_only_returns_none():
    assert clean_text('   \n\t  ') is None


def test_number_converted_to_string():
    assert clean_text(42) == '42'


def test_script_tag_removed_with_content():
    assert clean_text('<script>alert(1)</script>Текст') == 'Текст'


def test_style_tag_removed_with_content():
    assert clean_text('<style>body{color:red}</style>Текст') == 'Текст'


def test_html_tags_stripped_text_preserved():
    assert clean_text('<b>Важно</b> и <br/>ещё') == 'Важно и ещё'


def test_html_entities_decoded():
    assert clean_text('&laquo;Привет&raquo;') == '«Привет»'


def test_nbsp_becomes_space():
    result = clean_text('слово&nbsp;слово')
    assert result == 'слово слово'


def test_multiple_spaces_collapsed():
    assert clean_text('один   два\n\nтри') == 'один два три'


def test_leading_trailing_spaces_stripped():
    assert clean_text('  текст  ') == 'текст'


def test_control_characters_removed():
    # \x00 — null-байт, должен исчезнуть
    assert clean_text('до\x00после') == 'допосле'


def test_tab_and_newline_preserved_as_space():
    # \t и \n — разрешённые символы, схлопываются в пробел
    result = clean_text('a\tb\nc')
    assert result == 'a b c'


def test_normal_text_unchanged():
    assert clean_text('Обычный текст') == 'Обычный текст'


def test_mixed_html_and_text():
    result = clean_text('<p>Привет, <b>мир</b>!</p>')
    assert result == 'Привет, мир !'
