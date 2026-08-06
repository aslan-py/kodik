"""Тесты для HtmlCleaner, StructuredChunker и ResultMerger."""

from src.bp1.adaptive.processing.chunker import Chunk, StructuredChunker
from src.bp1.adaptive.processing.html_cleaner import HtmlCleaner
from src.bp1.adaptive.processing.merger import ResultMerger

from .constants import (
    CHUNK_BLOCKS_COUNT,
    CHUNK_CONTENT_REPEAT,
    CHUNK_MAX_SIZE_CHARS,
    CHUNK_MAX_SIZE_MULTI,
    CHUNK_MAX_SIZE_SINGLE,
    CHUNK_OVERLAP_CHARS,
    CHUNK_OVERLAP_MULTI,
    CHUNK_OVERLAP_SINGLE,
    CHUNK_TEST_CONTENT,
    CHUNK_TEST_CONTENT_SIZE,
    DEDUP_KEY_URL,
    HTML_CLEANER_MIN_TEXT_LENGTH,
    HTML_CLEANER_SHORT_MIN_TEXT_LENGTH,
    MERGER_CONFIDENCE_AVG,
    MERGER_CONFIDENCE_HIGH,
    MERGER_CONFIDENCE_LOW,
    MERGER_DUPLICATE_COUNT,
    MERGER_FALLBACK_CONFIDENCE_A,
    MERGER_FALLBACK_CONFIDENCE_B,
    MERGER_TOTAL_ITEMS,
    MERGER_UNIQUE_ITEMS,
)

# ============================================================================
# HtmlCleaner
# ============================================================================


def test_html_cleaner_removes_noise():
    """HtmlCleaner удаляет script/style/nav и JS-атрибуты."""
    html = """
    <html><head><title>Тест</title></head><body>
      <script>var x = 1;</script>
      <style>.a { color: red; }</style>
      <nav>Меню</nav>
      <article onclick="alert(1)">
        <h2>Заголовок</h2>
        <p>Достаточно длинный текст новости для анализа структуры.</p>
      </article>
    </body></html>
    """
    cleaner = HtmlCleaner(min_text_length=HTML_CLEANER_MIN_TEXT_LENGTH)
    result = cleaner.clean(html)

    assert 'script' not in result['content']
    assert 'style' not in result['content']
    assert 'nav' not in result['content']
    assert 'onclick' not in result['content']
    assert result['metadata'].get('title') == 'Тест'
    assert result['stats']['cleaned_size'] < result['stats']['original_size']


def test_html_cleaner_extracts_blocks():
    """HtmlCleaner собирает логические блоки для чанкирования."""
    html = """
    <html><body>
      <article><p>Первый блок с достаточно длинным текстом.</p></article>
      <article><p>Второй блок с достаточно длинным текстом.</p></article>
    </body></html>
    """
    cleaner = HtmlCleaner(min_text_length=HTML_CLEANER_SHORT_MIN_TEXT_LENGTH)
    result = cleaner.clean(html)

    assert len(result['blocks']) >= 2
    assert result['stats']['block_count'] >= 2


# ============================================================================
# StructuredChunker
# ============================================================================


def test_chunker_single_chunk():
    """Маленький контент помещается в один чанк."""
    chunker = StructuredChunker(
        max_chunk_size=CHUNK_MAX_SIZE_SINGLE, overlap_size=CHUNK_OVERLAP_SINGLE
    )
    cleaned = {
        'content': '<p>Маленький контент</p>',
        'blocks': [
            {'html': '<p>Маленький контент</p>', 'tag': 'p', 'classes': []},
        ],
    }
    chunks = chunker.chunk(cleaned)
    assert len(chunks) == 1
    assert chunks[0].size <= CHUNK_MAX_SIZE_SINGLE


def test_chunker_multiple_chunks_with_overlap():
    """Большой контент разбивается на чанки с перекрытием."""
    chunker = StructuredChunker(
        max_chunk_size=CHUNK_MAX_SIZE_MULTI, overlap_size=CHUNK_OVERLAP_MULTI
    )
    blocks = [
        {
            'html': f'<p>Блок {i} с текстом для чанкирования.</p>',
            'tag': 'p',
            'classes': [],
        }
        for i in range(CHUNK_BLOCKS_COUNT)
    ]
    cleaned = {'content': '', 'blocks': blocks}
    chunks = chunker.chunk(cleaned)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.size <= CHUNK_MAX_SIZE_MULTI


def test_chunker_chunk_by_chars():
    """Чанкирование по символам без структурированных блоков."""
    chunker = StructuredChunker(
        max_chunk_size=CHUNK_MAX_SIZE_CHARS, overlap_size=CHUNK_OVERLAP_CHARS
    )
    content = 'x' * CHUNK_CONTENT_REPEAT
    cleaned = {'content': content, 'blocks': []}
    chunks = chunker.chunk(cleaned)

    assert len(chunks) > 1
    assert all(c.size <= CHUNK_MAX_SIZE_CHARS for c in chunks)


def test_chunk_dataclass():
    """Chunk вычисляет size автоматически."""
    chunk = Chunk(
        index=0,
        content=CHUNK_TEST_CONTENT,
        start_block=0,
        end_block=0,
        metadata={},
    )
    assert chunk.size == CHUNK_TEST_CONTENT_SIZE


# ============================================================================
# ResultMerger
# ============================================================================


def test_merger_deduplicates_by_url():
    """ResultMerger удаляет дубликаты по url."""
    merger = ResultMerger(dedup_key=DEDUP_KEY_URL)
    results = [
        {
            'items': [
                {'url': 'https://example.com/1', 'title': 'Новость 1'},
                {'url': 'https://example.com/2', 'title': 'Новость 2'},
            ],
            'confidence': MERGER_CONFIDENCE_HIGH,
        },
        {
            'items': [
                {'url': 'https://example.com/1', 'title': 'Дубль 1'},
                {'url': 'https://example.com/3', 'title': 'Новость 3'},
            ],
            'confidence': MERGER_CONFIDENCE_LOW,
        },
    ]
    merged = merger.merge(results)

    assert merged['total_items_found'] == MERGER_TOTAL_ITEMS
    assert merged['duplicate_count'] == MERGER_DUPLICATE_COUNT
    assert len(merged['items']) == MERGER_UNIQUE_ITEMS
    assert merged['confidence'] == MERGER_CONFIDENCE_AVG


def test_merger_deduplicates_by_title():
    """ResultMerger использует title+published_at как fallback-ключ."""
    merger = ResultMerger(dedup_key=DEDUP_KEY_URL)
    results = [
        {
            'items': [
                {'title': 'Новость', 'published_at': '2026-01-01'},
            ],
            'confidence': MERGER_FALLBACK_CONFIDENCE_A,
        },
        {
            'items': [
                {'title': 'Новость', 'published_at': '2026-01-01'},
            ],
            'confidence': MERGER_FALLBACK_CONFIDENCE_B,
        },
    ]
    merged = merger.merge(results)

    assert len(merged['items']) == 1
    assert merged['duplicate_count'] == MERGER_DUPLICATE_COUNT


def test_merger_handles_empty():
    """ResultMerger обрабатывает пустой список результатов."""
    merger = ResultMerger()
    merged = merger.merge([])
    assert merged['items'] == []
    assert merged['chunks_processed'] == 0
    assert merged['confidence'] == 0.0
