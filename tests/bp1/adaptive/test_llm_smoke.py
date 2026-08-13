"""Smoke-тест LLM-модуля пакета BP-1 Adaptive (перевод из llm_test.py).

Воспроизводит все стадии бывшего скрипта ``src/bp1/adaptive/llm_test.py``
в виде детерминированных pytest-тестов:

1. ``SourceClassifier.classify``      — классификация источника.
2. ``LLMClient.analyze_structure``    — полный анализ структуры
   (с авто-чанкированием).
3. ``LLMClient.analyze_structure_chunked`` — явное чанкирование (HtmlCleaner →
   StructuredChunker → параллельное извлечение → ResultMerger).
4. ``LLMClient._llm_analyze``         — прямой анализ одним запросом.
5. ``AIAgent.choose_strategy``        — выбор стратегии обхода.
6. ``AIAgent.analyze_result``         — анализ результата парсинга.

В отличие от исходного скрипта, тесты НЕ обращаются к реальному LLM:
реальные вызовы ``openai.AsyncOpenAI`` подменяются фейком (как в
``test_llm.py``), а без ключа API используется эвристический fallback.
Это делает тесты быстрыми, детерминированными и не зависящими от сети/ключа.

HTML-страницы берутся из ``src/bp1/data/html_pages``. Если папка пуста или
отсутствует — тесты пропускаются (``skip``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from core.config import settings
from src.bp1.adaptive.processing.html_cleaner import HtmlCleaner
from src.bp1.adaptive.processing.llm import AIAgent, LLMClient
from src.bp1.adaptive.processing.merger import ResultMerger
from src.bp1.adaptive.schemas import (
    AdapterConfig,
    SourceClassification,
    StrategyType,
)
from src.bp1.adaptive.strategies.classifier import SourceClassifier

from .constants import (
    CONTAINER_SELECTOR_VALUE,
    ENCODING_ERRORS_REPLACE,
    ENCODING_UTF8,
    EXPECTED_FIELDS_SMOKE,
    FAKE_LLM_ERROR,
    HTML_GLOB,
    LLM_CHUNK_MAX_SIZE,
    LLM_CHUNK_OVERLAP,
    LLM_CONFIDENCE_HIGH,
    LLM_CONFIDENCE_LOW,
    LLM_DEFAULT_CONFIDENCE,
    MODULE_OPENAI,
    RECOMMENDATION_IMPROVE,
    RECOMMENDATION_NO_LLM,
    SCHEMA_TYPE_STRING,
    SELECTOR_TITLE_VALUE,
    SELECTOR_URL_VALUE,
    SMOKE_COMPETITOR,
    SOURCE_TYPE_VALUES,
    TEST_API_KEY,
)

# Корень проекта kodik/ — четыре уровня вверх от этого файла.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Папка с сохранёнными HTML-страницами (см. core.config: bp1_html_dir).
HTML_DIR = PROJECT_ROOT / 'src' / 'bp1' / 'data' / 'html_pages'


# ---------------------------------------------------------------------------
# Вспомогательные фикстуры и фейки
# ---------------------------------------------------------------------------


def _pick_html() -> Path:
    """Возвращает первый HTML-файл из data/html_pages."""
    if not HTML_DIR.exists():
        raise FileNotFoundError(f'Папка не найдена: {HTML_DIR}')
    files = sorted(HTML_DIR.glob(HTML_GLOB))
    if not files:
        raise FileNotFoundError(f'В папке нет HTML-файлов: {HTML_DIR}')
    return files[0]


@pytest.fixture(scope='module')
def html_page() -> tuple[str, str]:
    """Читает первый HTML-файл и возвращает (html, source_name)."""
    try:
        html_path = _pick_html()
    except FileNotFoundError as e:
        pytest.skip(str(e))
    html = html_path.read_text(
        encoding=ENCODING_UTF8, errors=ENCODING_ERRORS_REPLACE
    )
    source_name = html_path.name.split('_')[0]  # например, 'fedresurs'
    return html, source_name


class _FakeCompletion:
    """Фейковый ответ openai chat.completions.create."""

    def __init__(self, content: str):
        self.choices = [
            type(
                'Choice',
                (),
                {'message': type('Message', (), {'content': content})()},
            )()
        ]


class _FakeCompletions:
    """Фейковый объект chat.completions."""

    def __init__(self, content: str):
        self._content = content
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeCompletion(self._content)


class _FakeChat:
    """Фейковый объект chat."""

    def __init__(self, content: str):
        self.completions = _FakeCompletions(content)


class _FakeAsyncOpenAI:
    """Фейковый клиент AsyncOpenAI (см. test_llm.py)."""

    _content = ''

    def __init__(self, content: str = '', **kwargs):
        if content:
            self._content = content
        self._chat = _FakeChat(self._content)
        self.last_kwargs = None

    @property
    def chat(self):
        return self._chat

    @property
    def completions(self):
        return self._chat.completions


def _install_fake_openai(monkeypatch, content: str):
    """Подменить openai.AsyncOpenAI фейком с заданным ответом."""
    fake = ModuleType(MODULE_OPENAI)

    class FakeAsyncOpenAI(_FakeAsyncOpenAI):
        _content = content

    fake.AsyncOpenAI = FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, MODULE_OPENAI, fake)
    return FakeAsyncOpenAI


# ---------------------------------------------------------------------------
# 1. Классификация источника
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_classify(html_page):
    """SourceClassifier классифицирует реальную HTML-страницу."""
    html, source_name = html_page
    classifier = SourceClassifier()
    classification = await classifier.classify(
        source_name=source_name,
        source_url=f'https://{source_name}/',
        html=html,
    )
    assert isinstance(classification, SourceClassification)
    assert classification.source_name == source_name
    assert classification.source_type.value in SOURCE_TYPE_VALUES
    assert 0.0 <= classification.complexity_score <= 1.0
    assert isinstance(classification.has_antibot, bool)
    assert isinstance(classification.has_captcha, bool)
    assert isinstance(classification.is_spa, bool)
    assert classification.recommended_strategy in {
        s.value for s in StrategyType
    }


# ---------------------------------------------------------------------------
# 2. Полный анализ структуры (с авто-чанкированием)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_analyze_structure_heuristic(html_page, monkeypatch):
    """analyze_structure без ключа API использует эвристический fallback."""
    html, _ = html_page
    monkeypatch.setattr(settings, 'llm_api_key', None)
    client = LLMClient()
    config = await client.analyze_structure(
        html=html,
        competitor=SMOKE_COMPETITOR,
        expected_fields=EXPECTED_FIELDS_SMOKE,
    )
    assert isinstance(config, AdapterConfig)
    assert config.adaptive is True
    # Fallback: селектор url задан, чтобы работала эвристика по ссылкам.
    assert config.selectors.get('url') == SELECTOR_URL_VALUE
    assert 'title' in config.expected_schema
    assert 'url' in config.expected_schema


@pytest.mark.asyncio
async def test_smoke_analyze_structure_real_path(html_page, monkeypatch):
    """analyze_structure с ключом API вызывает OpenAI и парсит JSON."""
    html, _ = html_page
    monkeypatch.setattr(settings, 'llm_api_key', TEST_API_KEY)
    _install_fake_openai(
        monkeypatch,
        '{"selectors": {"container": "div.item", "title": "h2"}, '
        '"schema": {"title": "string", "url": "string"}, '
        '"confidence": 0.9}',
    )
    client = LLMClient()
    config = await client.analyze_structure(
        html=html,
        competitor=SMOKE_COMPETITOR,
        expected_fields=EXPECTED_FIELDS_SMOKE,
    )
    assert isinstance(config, AdapterConfig)
    assert config.selectors.get('container') == CONTAINER_SELECTOR_VALUE
    assert config.selectors.get('title') == SELECTOR_TITLE_VALUE
    assert config.expected_schema.get('title') == SCHEMA_TYPE_STRING
    assert config.confidence == LLM_CONFIDENCE_HIGH


# ---------------------------------------------------------------------------
# 3. Явное чанкирование (HtmlCleaner → StructuredChunker → извлечение → merger)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_chunked_pipeline(html_page, monkeypatch):
    """Полный конвейер чанкирования работает на реальной странице."""
    html, _ = html_page
    monkeypatch.setattr(settings, 'llm_api_key', TEST_API_KEY)
    _install_fake_openai(
        monkeypatch,
        '{"selectors": {"container": "div.item", "title": "h2"}, '
        '"schema": {"title": "string"}, "confidence": 0.8}',
    )

    client = LLMClient(
        max_chunk_size=LLM_CHUNK_MAX_SIZE, overlap_size=LLM_CHUNK_OVERLAP
    )

    # Этап 1: очистка HTML.
    cleaner = HtmlCleaner()
    cleaned = cleaner.clean(html)
    stats = cleaned.get('stats', {})
    assert stats.get('original_size', 0) >= 0
    assert stats.get('cleaned_size', 0) >= 0

    # Этап 2: чанкирование.
    chunker = client._chunker
    chunks = chunker.chunk(cleaned)
    assert isinstance(chunks, list)
    for chunk in chunks:
        assert chunk.size >= 0
        assert chunk.index >= 0

    # Этап 3: параллельное извлечение через LLM.
    results = await client._extract_from_chunks(
        chunks, SMOKE_COMPETITOR, EXPECTED_FIELDS_SMOKE
    )
    assert isinstance(results, list)
    assert len(results) <= len(chunks)

    # Этап 4: объединение результатов.
    merger = ResultMerger()
    merged = merger.merge(
        results=results,
        chunk_metadata=[c.metadata for c in chunks],
    )
    assert 'chunks_processed' in merged
    assert 'total_items_found' in merged
    assert 'duplicate_count' in merged
    assert 'confidence' in merged

    # Итоговый AdapterConfig.
    config = client._to_adapter_config(merged, EXPECTED_FIELDS_SMOKE)
    assert isinstance(config, AdapterConfig)
    assert config.adaptive is True


# ---------------------------------------------------------------------------
# 4. Прямой анализ одним запросом (_llm_analyze)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_llm_analyze_direct(html_page, monkeypatch):
    """_llm_analyze обрабатывает реальный HTML одним запросом."""
    html, _ = html_page
    monkeypatch.setattr(settings, 'llm_api_key', TEST_API_KEY)
    _install_fake_openai(
        monkeypatch,
        '{"selectors": {"container": "div.item"}, '
        '"schema": {"title": "string"}, "confidence": 0.7}',
    )
    client = LLMClient()
    config = await client._llm_analyze(
        html=html[: client._max_chunk_size],
        competitor=SMOKE_COMPETITOR,
        expected_fields=EXPECTED_FIELDS_SMOKE,
    )
    assert isinstance(config, AdapterConfig)
    assert config.selectors.get('container') == CONTAINER_SELECTOR_VALUE
    assert config.confidence == LLM_CONFIDENCE_LOW


@pytest.mark.asyncio
async def test_smoke_llm_analyze_fallback_on_error(html_page, monkeypatch):
    """При ошибке OpenAI _llm_analyze пробрасывает исключение, а вызывающий
    код переключается на эвристический fallback (как в llm_test.py)."""
    html, _ = html_page
    monkeypatch.setattr(settings, 'llm_api_key', TEST_API_KEY)

    fake = ModuleType(MODULE_OPENAI)

    class FailingAsyncOpenAI:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            return _FailingChat()

    class _FailingChat:
        @property
        def completions(self):
            return _FailingCompletions()

    class _FailingCompletions:
        async def create(self, **kwargs):
            raise RuntimeError(FAKE_LLM_ERROR)

    fake.AsyncOpenAI = FailingAsyncOpenAI
    monkeypatch.setitem(sys.modules, MODULE_OPENAI, fake)

    client = LLMClient()
    # _llm_analyze не перехватывает ошибку — она пробрасывается наружу.
    with pytest.raises(RuntimeError, match=FAKE_LLM_ERROR):
        await client._llm_analyze(
            html=html[: client._max_chunk_size],
            competitor=SMOKE_COMPETITOR,
            expected_fields=EXPECTED_FIELDS_SMOKE,
        )

    # Вызывающий код (как в llm_test.py) переключается на эвристику.
    # В реальном analyze_structure expected_fields заполняется дефолтными
    # полями, поэтому передаём непустой список.
    config = client._heuristic_analyze(html, ['title', 'url'])
    assert isinstance(config, AdapterConfig)
    assert config.selectors.get('url') == SELECTOR_URL_VALUE
    assert 'title' in config.expected_schema
    assert 'url' in config.expected_schema


# ---------------------------------------------------------------------------
# 5-6. AIAgent: выбор стратегии и анализ результата
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_agent_choose_strategy_heuristic(html_page, monkeypatch):
    """AIAgent без ключа API выбирает стратегию эвристически."""
    html, source_name = html_page
    monkeypatch.setattr(settings, 'llm_api_key', None)
    agent = AIAgent()
    classification = await SourceClassifier().classify(
        source_name=source_name,
        source_url=f'https://{source_name}/',
        html=html,
    )
    strategy = await agent.choose_strategy(classification)
    assert strategy in StrategyType


@pytest.mark.asyncio
async def test_smoke_agent_choose_strategy_real_path(html_page, monkeypatch):
    """AIAgent с ключом API выбирает стратегию из ответа LLM."""
    html, source_name = html_page
    monkeypatch.setattr(settings, 'llm_api_key', TEST_API_KEY)
    _install_fake_openai(monkeypatch, '{"strategy": "BROWSER"}')
    agent = AIAgent()
    classification = await SourceClassifier().classify(
        source_name=source_name,
        source_url=f'https://{source_name}/',
        html=html,
    )
    strategy = await agent.choose_strategy(classification)
    assert strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_smoke_agent_analyze_result(html_page, monkeypatch):
    """AIAgent анализирует результат парсинга (fallback и реальный путь)."""
    html, source_name = html_page

    # Fallback без ключа.
    monkeypatch.setattr(settings, 'llm_api_key', None)
    agent = AIAgent()
    items = [
        {'title': 'Пример записи 1', 'url': 'https://example.com/1'},
        {'title': 'Пример записи 2', 'url': 'https://example.com/2'},
    ]
    result = await agent.analyze_result(html, items, source_name)
    assert result['recommendation'] == RECOMMENDATION_NO_LLM
    assert result['confidence'] == LLM_DEFAULT_CONFIDENCE

    # Реальный путь с ключом.
    monkeypatch.setattr(settings, 'llm_api_key', TEST_API_KEY)
    _install_fake_openai(
        monkeypatch,
        '{"recommendation": "improve_selectors", "confidence": 0.9}',
    )
    agent = AIAgent()
    result = await agent.analyze_result(html, items, source_name)
    assert result['recommendation'] == RECOMMENDATION_IMPROVE
    assert result['confidence'] == LLM_CONFIDENCE_HIGH
