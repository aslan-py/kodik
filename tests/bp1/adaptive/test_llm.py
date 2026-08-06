"""Тесты для LLMClient и AIAgent (llm.py)."""

import sys
from types import ModuleType

import pytest

from src.bp1.adaptive.llm import AIAgent, LLMClient
from src.bp1.adaptive.schemas import (
    SourceClassification,
    SourceType,
    StrategyType,
)


class _FakeCompletion:
    """Фейковый ответ litellm.acompletion."""

    def __init__(self, content: str):
        self.choices = [
            type(
                'Choice',
                (),
                {'message': type('Message', (), {'content': content})()},
            )()
        ]


def _install_fake_litellm(monkeypatch, content: str):
    """Подменить модуль litellm фейком с заданным ответом acompletion.

    Возвращает фейковый модуль, чтобы тест мог проверить аргументы вызова.
    """
    fake = ModuleType('litellm')

    async def fake_acompletion(**kwargs):
        fake.last_kwargs = kwargs
        return _FakeCompletion(content)

    fake.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, 'litellm', fake)
    return fake


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
async def test_agent_analyze_result_without_llm():
    """AIAgent без LLM возвращает рекомендацию no_llm."""
    agent = AIAgent()
    result = await agent.analyze_result(
        '<html></html>',
        [{'title': 'Новость'}],
        'example.com',
    )
    assert result['recommendation'] == 'no_llm'


# ============================================================================
# Реальный LLM-путь (с моком litellm.acompletion)
# ============================================================================


@pytest.mark.asyncio
async def test_llm_analyze_structure_real_path(monkeypatch):
    """LLMClient с ключом API вызывает litellm и парсит JSON-ответ."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')
    fake = _install_fake_litellm(
        monkeypatch,
        '{"selectors": {"container": "div.item"}, '
        '"schema": {"title": "string", "url": "string"}}',
    )

    client = LLMClient()
    config = await client.analyze_structure(
        '<html><body><div class="item">Новость</div></body></html>',
        competitor='ООО АРХИТЕХ',
    )

    # Проверяем, что litellm действительно вызывался.
    assert fake.last_kwargs['model'] == 'gpt-4o-mini'
    assert fake.last_kwargs['temperature'] == 0.0
    # Схема берётся из ответа LLM.
    assert config.expected_schema == {
        'title': 'string',
        'url': 'string',
    }
    assert config.adaptive is True


@pytest.mark.asyncio
async def test_llm_analyze_structure_fallback_on_error(monkeypatch):
    """При ошибке litellm LLMClient переключается на эвристику."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')

    fake = ModuleType('litellm')

    async def failing_acompletion(**kwargs):
        raise RuntimeError('llm unavailable')

    fake.acompletion = failing_acompletion
    monkeypatch.setitem(sys.modules, 'litellm', fake)

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
    fake = _install_fake_litellm(monkeypatch, '{"strategy": "BROWSER"}')

    agent = AIAgent()
    classification = SourceClassification(
        source_name='example.com',
        source_type=SourceType.SPA,
        is_spa=True,
    )
    strategy = await agent.choose_strategy(classification)

    assert fake.last_kwargs['model'] == 'gpt-4o-mini'
    assert strategy == StrategyType.BROWSER


@pytest.mark.asyncio
async def test_agent_choose_strategy_fallback_on_invalid(monkeypatch):
    """При невалидной стратегии из LLM AIAgent использует эвристику."""
    monkeypatch.setenv('LLM_API_KEY', 'sk-test')
    _install_fake_litellm(monkeypatch, '{"strategy": "NOT_A_STRATEGY"}')

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
    _install_fake_litellm(
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
