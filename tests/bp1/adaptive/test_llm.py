"""Тесты для LLMClient и AIAgent (llm.py)."""

import sys
from types import ModuleType

import pytest

from src.bp1.adaptive.processing.llm import AIAgent, LLMClient, _default_model
from src.bp1.adaptive.schemas import (
    SiteType,
    SourceClassification,
    SourceType,
    StrategyType,
)

from .constants import (
    COMPETITOR,
    CONTAINER_SELECTOR_VALUE,
    ENV_LLM_API_KEY,
    ENV_OPENAI_API_KEY,
    EXAMPLE_SOURCE_NAME,
    FAKE_LLM_ERROR,
    HTML_EMPTY,
    HTML_WITH_LINK,
    LLM_CHUNK_MAX_SIZE,
    LLM_CHUNK_OVERLAP,
    LLM_CONFIDENCE_HIGH,
    LLM_ITEM_REPEAT,
    LLM_TEMPERATURE,
    MODULE_OPENAI,
    RECOMMENDATION_IMPROVE,
    RECOMMENDATION_NO_LLM,
    SCHEMA_TYPE_STRING,
    SELECTOR_TITLE_VALUE,
    SELECTOR_URL_VALUE,
    TEST_API_KEY,
)


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
    """Фейковый клиент AsyncOpenAI.

    Возвращает клиент с chat.completions.create, который отвечает заданным
    контентом. Сохраняет аргументы последнего вызова create.

    ``_content`` хранится на уровне класса, чтобы экземпляр, создаваемый
    лениво через ``_get_client()`` (без передачи content), отвечал тем же
    контентом. ``_chat`` создаётся один раз, чтобы ``last_kwargs``
    сохранялся между вызовами.
    """

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
    """Подменить openai.AsyncOpenAI фейком с заданным ответом.

    Возвращает фейковый класс, чтобы тест мог проверить аргументы вызова.
    """
    fake = ModuleType(MODULE_OPENAI)

    class FakeAsyncOpenAI(_FakeAsyncOpenAI):
        _content = content

    fake.AsyncOpenAI = FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, MODULE_OPENAI, fake)
    return FakeAsyncOpenAI


@pytest.mark.asyncio
async def test_llm_analyze_structure_heuristic():
    """LLMClient без конфигурации использует эвристический fallback."""
    client = LLMClient()
    config = await client.analyze_structure(
        HTML_WITH_LINK,
        competitor=COMPETITOR,
    )
    assert 'title' in config.expected_schema
    assert 'url' in config.expected_schema
    assert config.adaptive is True


def test_parse_json_handles_markdown():
    """_parse_json извлекает JSON из markdown-обёртки."""
    content = '```json\n{"strategy": "BROWSER"}\n```'
    data = LLMClient._parse_json(content)
    assert data == {'strategy': 'BROWSER'}


def test_parse_json_handles_plain():
    """_parse_json обрабатывает чистый JSON."""
    data = LLMClient._parse_json('{"a": 1}')
    assert data == {'a': 1}


def test_parse_json_handles_invalid():
    """_parse_json возвращает пустой словарь для невалидного JSON."""
    data = LLMClient._parse_json('not json')
    assert data == {}


@pytest.mark.asyncio
async def test_agent_choose_strategy_heuristic_captcha(monkeypatch):
    """AIAgent выбирает STEALTH при наличии CAPTCHA."""
    # Очищаем ключи, чтобы гарантировать fallback (не зависеть от .env).
    monkeypatch.delenv(ENV_LLM_API_KEY, raising=False)
    monkeypatch.delenv(ENV_OPENAI_API_KEY, raising=False)
    agent = AIAgent()
    classification = SourceClassification(
        source_name=EXAMPLE_SOURCE_NAME,
        source_type=SourceType.NEWS,
        has_captcha=True,
    )
    strategy = await agent.choose_strategy(classification)
    assert strategy == StrategyType.STEALTH


@pytest.mark.asyncio
async def test_agent_choose_strategy_heuristic_spa(monkeypatch):
    """AIAgent выбирает BROWSER для SPA."""
    # Очищаем ключи, чтобы гарантировать fallback (не зависеть от .env).
    monkeypatch.delenv(ENV_LLM_API_KEY, raising=False)
    monkeypatch.delenv(ENV_OPENAI_API_KEY, raising=False)
    agent = AIAgent()
    classification = SourceClassification(
        source_name=EXAMPLE_SOURCE_NAME,
        source_type=SourceType.SPA,
        is_spa=True,
    )
    strategy = await agent.choose_strategy(classification)
    assert strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_agent_analyze_result_without_llm(monkeypatch):
    """AIAgent без LLM возвращает рекомендацию no_llm."""
    # Очищаем ключи, чтобы гарантировать fallback (не зависеть от .env).
    monkeypatch.delenv(ENV_LLM_API_KEY, raising=False)
    monkeypatch.delenv(ENV_OPENAI_API_KEY, raising=False)
    agent = AIAgent()
    result = await agent.analyze_result(
        HTML_EMPTY,
        [{'title': 'Новость'}],
        EXAMPLE_SOURCE_NAME,
    )
    assert result['recommendation'] == RECOMMENDATION_NO_LLM


# ============================================================================
# Реальный LLM-путь (с моком openai.AsyncOpenAI)
# ============================================================================


@pytest.mark.asyncio
async def test_llm_analyze_structure_real_path(monkeypatch):
    """LLMClient с ключом API вызывает OpenAI и парсит JSON-ответ."""
    monkeypatch.setenv(ENV_LLM_API_KEY, TEST_API_KEY)
    _install_fake_openai(
        monkeypatch,
        '{"selectors": {"container": "div.item"}, '
        '"schema": {"title": "string", "url": "string"}, '
        '"confidence": 0.9}',
    )

    client = LLMClient()
    config = await client.analyze_structure(
        '<html><body><div class="item">Новость</div></body></html>',
        competitor=COMPETITOR,
    )

    # Проверяем, что OpenAI действительно вызывался.
    last_kwargs = client._client.chat.completions.last_kwargs
    assert last_kwargs['model'] == _default_model()
    assert last_kwargs['temperature'] == LLM_TEMPERATURE
    # Схема берётся из ответа LLM.
    assert config.expected_schema == {
        'title': SCHEMA_TYPE_STRING,
        'url': SCHEMA_TYPE_STRING,
    }
    # Реальные CSS-селекторы из ответа LLM (не пустые строки).
    assert config.selectors == {'container': CONTAINER_SELECTOR_VALUE}
    assert config.confidence == LLM_CONFIDENCE_HIGH
    assert config.adaptive is True


@pytest.mark.asyncio
async def test_llm_analyze_structure_chunked(monkeypatch):
    """LLMClient чанкирует большие HTML и объединяет результаты."""
    monkeypatch.setenv(ENV_LLM_API_KEY, TEST_API_KEY)

    # Большой HTML, который не помещается в один чанк.
    item = '<div class="item">Новость</div>'
    big_html = '<html><body>' + item * LLM_ITEM_REPEAT + '</body></html>'

    _install_fake_openai(
        monkeypatch,
        '{"selectors": {"container": "div.item", "title": "h2"}, '
        '"schema": {"title": "string"}, "confidence": 0.8}',
    )

    client = LLMClient(
        max_chunk_size=LLM_CHUNK_MAX_SIZE, overlap_size=LLM_CHUNK_OVERLAP
    )
    config = await client.analyze_structure(big_html, competitor=COMPETITOR)

    # Чанкирование должно вызвать OpenAI несколько раз.
    last_kwargs = client._client.chat.completions.last_kwargs
    assert last_kwargs['model'] == _default_model()
    # Селекторы объединены из чанков.
    assert config.selectors.get('container') == CONTAINER_SELECTOR_VALUE
    assert config.selectors.get('title') == SELECTOR_TITLE_VALUE
    assert config.adaptive is True


@pytest.mark.asyncio
async def test_llm_analyze_structure_heuristic_selectors(monkeypatch):
    """Эвристический fallback возвращает селектор url для ссылок."""
    # Очищаем ключи, чтобы гарантировать fallback (не зависеть от .env).
    monkeypatch.delenv(ENV_LLM_API_KEY, raising=False)
    monkeypatch.delenv(ENV_OPENAI_API_KEY, raising=False)
    client = LLMClient()
    config = await client.analyze_structure(
        HTML_WITH_LINK,
        competitor=COMPETITOR,
    )
    # Fallback: селектор url задан, чтобы работала эвристика по ссылкам.
    assert config.selectors.get('url') == SELECTOR_URL_VALUE
    assert 'title' in config.expected_schema


@pytest.mark.asyncio
async def test_llm_analyze_structure_fallback_on_error(monkeypatch):
    """При ошибке OpenAI LLMClient переключается на эвристику."""
    monkeypatch.setenv(ENV_LLM_API_KEY, TEST_API_KEY)

    fake = ModuleType(MODULE_OPENAI)

    class FailingAsyncOpenAI:
        def __init__(self, **kwargs):
            pass

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
    config = await client.analyze_structure(
        HTML_WITH_LINK,
        competitor=COMPETITOR,
    )

    # Fallback: схема из ожидаемых полей по умолчанию.
    assert 'title' in config.expected_schema
    assert 'url' in config.expected_schema


@pytest.mark.asyncio
async def test_agent_choose_strategy_real_path(monkeypatch):
    """AIAgent с ключом API выбирает стратегию из ответа LLM."""
    monkeypatch.setenv(ENV_LLM_API_KEY, TEST_API_KEY)
    _install_fake_openai(monkeypatch, '{"strategy": "BROWSER"}')

    agent = AIAgent()
    classification = SourceClassification(
        source_name=EXAMPLE_SOURCE_NAME,
        source_type=SourceType.SPA,
        is_spa=True,
    )
    strategy = await agent.choose_strategy(classification)

    last_kwargs = agent._client.chat.completions.last_kwargs
    assert last_kwargs['model'] == _default_model()
    assert strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_agent_choose_strategy_fallback_on_invalid(monkeypatch):
    """При невалидной стратегии из LLM AIAgent использует эвристику."""
    monkeypatch.setenv(ENV_LLM_API_KEY, TEST_API_KEY)
    _install_fake_openai(monkeypatch, '{"strategy": "NOT_A_STRATEGY"}')

    agent = AIAgent()
    classification = SourceClassification(
        source_name=EXAMPLE_SOURCE_NAME,
        source_type=SourceType.SPA,
        is_spa=True,
    )
    strategy = await agent.choose_strategy(classification)

    # Невалидная стратегия → эвристика: SPA → BROWSER.
    assert strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_agent_analyze_result_real_path(monkeypatch):
    """AIAgent с ключом API возвращает рекомендации из ответа LLM."""
    monkeypatch.setenv(ENV_LLM_API_KEY, TEST_API_KEY)
    _install_fake_openai(
        monkeypatch,
        '{"recommendation": "improve_selectors", "confidence": 0.9}',
    )

    agent = AIAgent()
    result = await agent.analyze_result(
        HTML_EMPTY,
        [{'title': 'Новость'}],
        EXAMPLE_SOURCE_NAME,
    )

    assert result['recommendation'] == RECOMMENDATION_IMPROVE
    assert result['confidence'] == LLM_CONFIDENCE_HIGH


@pytest.mark.asyncio
async def test_classify_with_llm_heuristic_fallback():
    """LLMClient без конфигурации использует эвристический fallback."""
    client = LLMClient()
    result = await client.classify_with_llm(HTML_EMPTY, EXAMPLE_SOURCE_NAME)

    assert result.source_name == EXAMPLE_SOURCE_NAME
    assert result.site_type in SiteType
    assert result.complexity_score >= 0.0


@pytest.mark.asyncio
async def test_classify_with_llm_real_path(monkeypatch):
    """LLMClient с ключом API возвращает классификацию из ответа LLM."""
    monkeypatch.setenv(ENV_LLM_API_KEY, TEST_API_KEY)
    _install_fake_openai(
        monkeypatch,
        '{'
        '"site_type": "e_commerce", '
        '"page_subtype": "detail", '
        '"confidence": 0.9, '
        '"business_features": {"has_payment": true, "has_cart": true}, '
        '"technical_features": {"is_spa": true, "frameworks": ["react"]}, '
        '"complexity_score": 0.6, '
        '"recommended_strategy": "BROWSER"'
        '}',
    )

    client = LLMClient()
    result = await client.classify_with_llm(
        '<html><body>магазин</body></html>', 'https://shop.example'
    )

    assert result.site_type == SiteType.E_COMMERCE
    assert result.page_subtype.value == 'detail'
    assert result.technical_features.is_spa is True
    assert result.technical_features.frameworks == ['react']
    assert result.business_features.has_payment is True
    assert result.complexity_score == 0.6
    assert result.recommended_strategy == 'BROWSER'
