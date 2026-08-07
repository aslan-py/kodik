"""Тесты для SourceClassifier."""

import pytest

from src.bp1.adaptive.classifier import SourceClassifier
from src.bp1.adaptive.schemas import SourceType, StrategyType


@pytest.mark.asyncio
async def test_classify_api_source():
    """API-источник классифицируется как API."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name='api.hh.ru',
        source_url='https://api.hh.ru/vacancies',
    )
    assert result.source_type == SourceType.API
    assert result.recommended_strategy == StrategyType.FAST.value


@pytest.mark.asyncio
async def test_classify_registry_source():
    """Реестровый источник классифицируется как REGISTRY."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name='fedresurs.ru',
        source_url='https://fedresurs.ru/entities',
    )
    assert result.source_type == SourceType.REGISTRY


@pytest.mark.asyncio
async def test_classify_news_source():
    """Новостной источник классифицируется как NEWS."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name='lenta.ru',
        source_url='https://lenta.ru/news',
    )
    assert result.source_type == SourceType.NEWS


@pytest.mark.asyncio
async def test_classify_captcha_leads_to_hitl():
    """Наличие CAPTCHA приводит к стратегии HITL."""
    classifier = SourceClassifier()
    html = '<html><body><div class="g-recaptcha"></div></body></html>'
    result = await classifier.classify(
        source_name='example.com',
        source_url='https://example.com',
        html=html,
    )
    assert result.has_captcha is True
    assert result.recommended_strategy == StrategyType.HITL.value


@pytest.mark.asyncio
async def test_classify_antibot_leads_to_stealth():
    """Наличие антибот-защиты приводит к стратегии STEALTH."""
    classifier = SourceClassifier()
    headers = {'Server': 'cloudflare', 'CF-RAY': 'abc123'}
    result = await classifier.classify(
        source_name='example.com',
        source_url='https://example.com',
        headers=headers,
    )
    assert result.has_antibot is True
    assert result.recommended_strategy == StrategyType.STEALTH.value


@pytest.mark.asyncio
async def test_classify_spa_leads_to_browser():
    """SPA-приложение классифицируется как SPA и приводит к BROWSER."""
    classifier = SourceClassifier()
    html = '<html><body><div id="app"></div></body></html>'
    result = await classifier.classify(
        source_name='example.com',
        source_url='https://example.com',
        html=html,
    )
    assert result.is_spa is True
    assert result.source_type == SourceType.SPA
    assert result.recommended_strategy == StrategyType.BROWSER.value


@pytest.mark.asyncio
async def test_classify_simple_leads_to_fast():
    """Простой источник приводит к стратегии FAST."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name='example.com',
        source_url='https://example.com',
    )
    assert result.recommended_strategy == StrategyType.FAST.value
    assert result.complexity_score < 0.5
