from types import SimpleNamespace

from core.enums import NormStatus, RejectReason, StopType
from src.bp2.pipeline import apply_filters, is_black_domain, match_stop_word


def sw(phrase, stop_type):
    """Заглушка StopWord — только нужные поля."""
    return SimpleNamespace(
        phrase=phrase, type=SimpleNamespace(value=stop_type.value)
    )


# --- is_black_domain ---


def test_domain_in_blacklist():
    assert is_black_domain('kompromat.ru', {'kompromat.ru', 'spam.ru'}) is True


def test_domain_not_in_blacklist():
    assert is_black_domain('forbes.ru', {'kompromat.ru'}) is False


def test_none_domain_returns_false():
    assert is_black_domain(None, {'kompromat.ru'}) is False


def test_empty_blacklist_returns_false():
    assert is_black_domain('kompromat.ru', set()) is False


# --- match_stop_word ---


def test_stop_word_found_in_title():
    words = [sw('реклама', StopType.stop_word)]
    reason = match_stop_word('Это реклама скидок', None, words)
    assert reason == RejectReason.stop_word


def test_stop_word_found_in_text():
    words = [sw('гороскоп', StopType.stop_topic)]
    reason = match_stop_word('Заголовок', 'Читайте гороскоп на неделю', words)
    assert reason == RejectReason.stop_topic


def test_stop_word_case_insensitive():
    words = [sw('реклама', StopType.stop_word)]
    reason = match_stop_word('РЕКЛАМА', None, words)
    assert reason == RejectReason.stop_word


def test_root_matches_word_form():
    words = [sw('наруш', StopType.stop_word)]
    reason = match_stop_word('Проверка выявила нарушений', None, words)
    assert reason == RejectReason.stop_word


def test_false_positive_type_preserved():
    words = [sw('бегемот в зоопарке', StopType.false_positive)]
    reason = match_stop_word('Бегемот в зоопарке Казани', None, words)
    assert reason == RejectReason.false_positive


def test_no_match_returns_none():
    words = [sw('реклама', StopType.stop_word)]
    assert (
        match_stop_word('Нормальный заголовок', 'Нормальный текст', words)
        is None
    )


def test_none_title_and_text_no_crash():
    words = [sw('реклама', StopType.stop_word)]
    assert match_stop_word(None, None, words) is None


def test_first_match_wins():
    words = [
        sw('реклама', StopType.stop_word),
        sw('гороскоп', StopType.stop_topic),
    ]
    reason = match_stop_word('реклама гороскоп', None, words)
    assert reason == RejectReason.stop_word


# --- apply_filters ---


def _row(
    status=NormStatus.ok,
    reason=None,
    domain='example.ru',
    title='Заголовок',
    text='Текст',
):
    return {
        'status': status,
        'reject_reason': reason,
        'media_domain': domain,
        'title': title,
        'text': text,
    }


def test_already_rejected_not_changed():
    row = _row(
        status=NormStatus.rejected,
        reason=RejectReason.parse_error,
        domain='kompromat.ru',
    )
    result = apply_filters(row, black_domains={'kompromat.ru'}, stop_words=[])
    assert result['reject_reason'] == RejectReason.parse_error


def test_black_domain_sets_rejected():
    row = _row(domain='kompromat.ru')
    result = apply_filters(row, black_domains={'kompromat.ru'}, stop_words=[])
    assert result['status'] == NormStatus.rejected
    assert result['reject_reason'] == RejectReason.black_domain


def test_black_domain_skips_stop_word_check():
    words = [sw('реклама', StopType.stop_word)]
    row = _row(domain='kompromat.ru', title='реклама')
    result = apply_filters(
        row, black_domains={'kompromat.ru'}, stop_words=words
    )
    assert result['reject_reason'] == RejectReason.black_domain


def test_stop_word_sets_rejected():
    words = [sw('реклама', StopType.stop_word)]
    row = _row(domain='ok.ru', title='Это реклама')
    result = apply_filters(row, black_domains=set(), stop_words=words)
    assert result['status'] == NormStatus.rejected
    assert result['reject_reason'] == RejectReason.stop_word


def test_clean_row_stays_ok():
    row = _row(domain='forbes.ru', title='Новость без шума')
    result = apply_filters(row, black_domains=set(), stop_words=[])
    assert result['status'] == NormStatus.ok
    assert result['reject_reason'] is None
