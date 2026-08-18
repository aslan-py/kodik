"""Тесты сборки промптов (src.bp1.adaptive.processing._llm.prompt_builders)."""

from src.bp1.adaptive.processing._llm.prompt_builders import (
    build_analysis_prompt,
    build_article_text_prompt,
    build_chunk_prompt,
    build_classification_prompt,
    build_result_analysis_prompt,
    build_strategy_prompt,
)
from src.bp1.adaptive.processing.chunker import Chunk


def test_build_classification_prompt_injects_values():
    """Промпт классификации подставляет URL, title, description, html."""
    prompt = build_classification_prompt(
        url='https://example.com',
        title='Заголовок',
        description='Описание',
        html='<body>контент</body>',
    )
    assert 'https://example.com' in prompt
    assert 'Заголовок' in prompt
    assert 'Описание' in prompt
    assert 'контент' in prompt


def test_build_analysis_prompt_contains_fields():
    """Промпт анализа структуры содержит конкурента и ожидаемые поля."""
    prompt = build_analysis_prompt(
        html='<html>...</html>',
        competitor='ООО АРХИТЕХ',
        expected_fields=['title', 'url'],
    )
    assert 'ООО АРХИТЕХ' in prompt
    assert 'title' in prompt
    assert 'url' in prompt
    assert 'selectors' in prompt


def test_build_chunk_prompt_injects_chunk_index():
    """Промпт чанка указывает индекс фрагмента."""
    chunk = Chunk(
        index=3,
        content='<div class="item">Новость</div>',
        start_block=1,
        end_block=2,
    )
    prompt = build_chunk_prompt(
        chunk, competitor='ООО', expected_fields=['title']
    )
    assert 'часть 3' in prompt
    assert '<div class="item">Новость</div>' in prompt


def test_build_article_text_prompt():
    """Промпт извлечения текста содержит HTML."""
    prompt = build_article_text_prompt('<p>Текст статьи</p>')
    assert '<p>Текст статьи</p>' in prompt


def test_build_strategy_prompt():
    """Промпт выбора стратегии содержит классификацию."""
    prompt = build_strategy_prompt('{"is_spa": true}')
    assert '{"is_spa": true}' in prompt
    assert 'FAST' in prompt


def test_build_result_analysis_prompt_truncates_examples():
    """Промпт анализа результата показывает не более 3 примеров."""
    items = [{'title': f'Новость {i}'} for i in range(5)]
    prompt = build_result_analysis_prompt('example.com', items)
    assert 'example.com' in prompt
    assert '5' in prompt  # item_count = len(items)
    # В examples сериализуются только первые 3.
    assert 'Новость 0' in prompt
    assert 'Новость 2' in prompt
    assert 'Новость 4' not in prompt
