"""Тесты для HtmlCleaner, StructuredChunker и ResultMerger."""

from src.bp1.adaptive.chunker import Chunk, StructuredChunker
from src.bp1.adaptive.html_cleaner import HtmlCleaner
from src.bp1.adaptive.merger import ResultMerger

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
    cleaner = HtmlCleaner(min_text_length=10)
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
    cleaner = HtmlCleaner(min_text_length=5)
    result = cleaner.clean(html)

    assert len(result['blocks']) >= 2
    assert result['stats']['block_count'] >= 2


# ============================================================================
# StructuredChunker
# ============================================================================


def test_chunker_single_chunk():
    """Маленький контент помещается в один чанк."""
    chunker = StructuredChunker(max_chunk_size=8000, overlap_size=500)
    cleaned = {
        'content': '<p>Маленький контент</p>',
        'blocks': [
            {'html': '<p>Маленький контент</p>', 'tag': 'p', 'classes': []},
        ],
    }
    chunks = chunker.chunk(cleaned)
    assert len(chunks) == 1
    assert chunks[0].size <= 8000


def test_chunker_multiple_chunks_with_overlap():
    """Большой контент разбивается на чанки с перекрытием."""
    chunker = StructuredChunker(max_chunk_size=100, overlap_size=20)
    blocks = [
        {
            'html': f'<p>Блок {i} с текстом для чанкирования.</p>',
            'tag': 'p',
            'classes': [],
        }
        for i in range(20)
    ]
    cleaned = {'content': '', 'blocks': blocks}
    chunks = chunker.chunk(cleaned)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.size <= 100


def test_chunker_chunk_by_chars():
    """Чанкирование по символам без структурированных блоков."""
    chunker = StructuredChunker(max_chunk_size=50, overlap_size=10)
    content = 'x' * 200
    cleaned = {'content': content, 'blocks': []}
    chunks = chunker.chunk(cleaned)

    assert len(chunks) > 1
    assert all(c.size <= 50 for c in chunks)


def test_chunk_dataclass():
    """Chunk вычисляет size автоматически."""
    chunk = Chunk(
        index=0, content='abc', start_block=0, end_block=0, metadata={}
    )
    assert chunk.size == 3


# ============================================================================
# ResultMerger
# ============================================================================


def test_merger_deduplicates_by_url():
    """ResultMerger удаляет дубликаты по url."""
    merger = ResultMerger(dedup_key='url')
    results = [
        {
            'items': [
                {'url': 'https://example.com/1', 'title': 'Новость 1'},
                {'url': 'https://example.com/2', 'title': 'Новость 2'},
            ],
            'confidence': 0.9,
        },
        {
            'items': [
                {'url': 'https://example.com/1', 'title': 'Дубль 1'},
                {'url': 'https://example.com/3', 'title': 'Новость 3'},
            ],
            'confidence': 0.8,
        },
    ]
    merged = merger.merge(results)

    assert merged['total_items_found'] == 4
    assert merged['duplicate_count'] == 1
    assert len(merged['items']) == 3
    assert merged['confidence'] == 0.85


def test_merger_deduplicates_by_title():
    """ResultMerger использует title+published_at как fallback-ключ."""
    merger = ResultMerger(dedup_key='url')
    results = [
        {
            'items': [
                {'title': 'Новость', 'published_at': '2026-01-01'},
            ],
            'confidence': 0.7,
        },
        {
            'items': [
                {'title': 'Новость', 'published_at': '2026-01-01'},
            ],
            'confidence': 0.6,
        },
    ]
    merged = merger.merge(results)

    assert len(merged['items']) == 1
    assert merged['duplicate_count'] == 1


def test_merger_handles_empty():
    """ResultMerger обрабатывает пустой список результатов."""
    merger = ResultMerger()
    merged = merger.merge([])
    assert merged['items'] == []
    assert merged['chunks_processed'] == 0
    assert merged['confidence'] == 0.0
