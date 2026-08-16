"""Тесты устойчивого разбора JSON (_llm.json_utils)."""

from src.bp1.adaptive.processing._llm.json_utils import parse_json


def test_plain_json():
    """Чистый JSON разбирается напрямую."""
    assert parse_json('{"a": 1}') == {'a': 1}


def test_markdown_fence_json():
    """JSON внутри ```json ... ``` блока."""
    assert parse_json('```json\n{"strategy": "BROWSER"}\n```') == {
        'strategy': 'BROWSER'
    }


def test_markdown_fence_plain():
    """JSON внутри ``` ... ``` без слова json."""
    assert parse_json('```\n{"a": 1}\n```') == {'a': 1}


def test_text_before_after_json():
    """Пояснения до и после JSON-объекта игнорируются."""
    content = 'Вот результат:\n{"a": 1}\nКонец.'
    assert parse_json(content) == {'a': 1}


def test_invalid_returns_empty():
    """Невалидный текст возвращает пустой словарь."""
    assert parse_json('not json') == {}


def test_empty_returns_empty():
    """Пустая строка возвращает пустой словарь."""
    assert parse_json('') == {}
    assert parse_json('   ') == {}


def test_nested_json_in_text():
    """Вложенный JSON с фигурными скобками внутри строк не ломает разбор."""
    content = '{"message": "содержит {скобки}", "a": 1}'
    assert parse_json(content) == {'message': 'содержит {скобки}', 'a': 1}


def test_non_dict_json_returns_empty():
    """JSON не-объект (например, массив) не принимается."""
    assert parse_json('[1, 2, 3]') == {}


def test_case_insensitive_fence():
    """Обёртка ```JSON``` (верхний регистр) обрабатывается."""
    assert parse_json('```JSON\n{"a": 1}\n```') == {'a': 1}
