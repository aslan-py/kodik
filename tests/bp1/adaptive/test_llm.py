"""Тесты для LLMClient и AIAgent (llm.py)."""

import sys
from types import ModuleType

import pytest

from src.bp1.adaptive.llm import AIAgent, LLMClient, _default_model
from src.bp1.adaptive.schemas import (
    SourceClassification,
    SourceType,
    StrategyType,
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
    fake = ModuleType('openai')

    class FakeAsyncOpenAI(_FakeAsyncOpenAI):
        _content = content

    fake.AsyncOpenAI = FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, 'openai', fake)
    return FakeAsyncOpenAI


@pytest.mark.asyncio
async def test_llm_analyze_structure_heuristic():
    """LLMClient без конфигурации использует эвристический fallback."""
    client = LLMClient()
    config = await client.analyze_structure(
        '<html><body><a href="/1">Новость</a></body></html>',
        competitor='ООО АРХИТЕХ',
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
async def test_agent_choose_strategy_heuristic_captcha():
    """AIAgent выбирает STEALTH при наличии CAPTCHA."""
    agent = AIAgent()
    classification = SourceClassification(
        source_name='example.com',
        source_type=SourceType.NEWS,
        has_captcha=True,
    )
    strategy = await agent.choose_strategy(classification)
    assert strategy == StrategyType.STEALTH


@pytest.mark.asyncio
async def test_agent_choose_strategy_heuristic_spa():
    """AIAgent выбирает BROWSER для SPA."""
    agent = AIAgent()
    classification = SourceClassification(
        source_name='example.com',
        source_type=SourceType.SPA,
        is_spa=True,
    )
    strategy = await agent.choose_strategy(classification)
    assert strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_agent_analyze_result_without_llm(monkeypatch):
    """AIAgent без LLM возвращает рекомендацию no_llm."""
    # Очищаем ключи, чтобы гарантировать fallback (не зависеть от .env).
    monkeypatch.delenv('LLM_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    agent = AIAgent()
    result = await agent.analyze_result(
        '<html></html>',
        [{'title': 'Новость'}],
        'example.com',
    )
    assert result['recommendation'] == 'no_llm'


# ============================================================================
# Реальный LLM-путь (с моком openai.AsyncOpenAI)
# ============================================================================


@pytest.mark.asyncio
async def test_llm_analyze_structure_real_path(monkeypatch):
    """LLMClient с ключом API вызывает OpenAI и парсит JSON-ответ."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')
    _install_fake_openai(
        monkeypatch,
        '{"selectors": {"container": "div.item"}, '
        '"schema": {"title": "string", "url": "string"}, '
        '"confidence": 0.9}',
    )

    client = LLMClient()
    config = await client.analyze_structure(
        '<html><body><div class="item">Новость</div></body></html>',
        competitor='ООО АРХИТЕХ',
    )

    # Проверяем, что OpenAI действительно вызывался.
    last_kwargs = client._client.chat.completions.last_kwargs
    assert last_kwargs['model'] == _default_model()
    assert last_kwargs['temperature'] == 0.0
    # Схема берётся из ответа LLM.
    assert config.expected_schema == {
        'title': 'string',
        'url': 'string',
    }
    # Реальные CSS-селекторы из ответа LLM (не пустые строки).
    assert config.selectors == {'container': 'div.item'}
    assert config.confidence == 0.9
    assert config.adaptive is True


@pytest.mark.asyncio
async def test_llm_analyze_structure_chunked(monkeypatch):
    """LLMClient чанкирует большие HTML и объединяет результаты."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')

    # Большой HTML, который не помещается в один чанк.
    item = '<div class="item">Новость</div>'
    big_html = '<html><body>' + item * 200 + '</body></html>'

    _install_fake_openai(
        monkeypatch,
        '{"selectors": {"container": "div.item", "title": "h2"}, '
        '"schema": {"title": "string"}, "confidence": 0.8}',
    )

    client = LLMClient(max_chunk_size=2000, overlap_size=200)
    config = await client.analyze_structure(big_html, competitor='ООО АРХИТЕХ')

    # Чанкирование должно вызвать OpenAI несколько раз.
    last_kwargs = client._client.chat.completions.last_kwargs
    assert last_kwargs['model'] == _default_model()
    # Селекторы объединены из чанков.
    assert config.selectors.get('container') == 'div.item'
    assert config.selectors.get('title') == 'h2'
    assert config.adaptive is True


@pytest.mark.asyncio
async def test_llm_analyze_structure_heuristic_selectors():
    """Эвристический fallback возвращает селектор url для ссылок."""
    client = LLMClient()
    config = await client.analyze_structure(
        '<html><body><a href="/1">Новость</a></body></html>',
        competitor='ООО АРХИТЕХ',
    )
    # Fallback: селектор url задан, чтобы работала эвристика по ссылкам.
    assert config.selectors.get('url') == 'a[href]'
    assert 'title' in config.expected_schema


@pytest.mark.asyncio
async def test_llm_analyze_structure_fallback_on_error(monkeypatch):
    """При ошибке OpenAI LLMClient переключается на эвристику."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')

    fake = ModuleType('openai')

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
            raise RuntimeError('llm unavailable')

    fake.AsyncOpenAI = FailingAsyncOpenAI
    monkeypatch.setitem(sys.modules, 'openai', fake)

    client = LLMClient()
    config = await client.analyze_structure(
        '<html><body><a href="/1">Новость</a></body></html>',
        competitor='ООО АРХИТЕХ',
    )

    # Fallback: схема из ожидаемых полей по умолчанию.
    assert 'title' in config.expected_schema
    assert 'url' in config.expected_schema


@pytest.mark.asyncio
async def test_agent_choose_strategy_real_path(monkeypatch):
    """AIAgent с ключом API выбирает стратегию из ответа LLM."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')
    _install_fake_openai(monkeypatch, '{"strategy": "BROWSER"}')

    agent = AIAgent()
    classification = SourceClassification(
        source_name='example.com',
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
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')
    _install_fake_openai(monkeypatch, '{"strategy": "NOT_A_STRATEGY"}')

    agent = AIAgent()
    classification = SourceClassification(
        source_name='example.com',
        source_type=SourceType.SPA,
        is_spa=True,
    )
    strategy = await agent.choose_strategy(classification)

    # Невалидная стратегия → эвристика: SPA → BROWSER.
    assert strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_agent_analyze_result_real_path(monkeypatch):
    """AIAgent с ключом API возвращает рекомендации из ответа LLM."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')
    _install_fake_openai(
        monkeypatch,
        '{"recommendation": "improve_selectors", "confidence": 0.9}',
    )

    agent = AIAgent()
    result = await agent.analyze_result(
        '<html></html>',
        [{'title': 'Новость'}],
        'example.com',
    )

    assert result['recommendation'] == 'improve_selectors'
    assert result['confidence'] == 0.9
