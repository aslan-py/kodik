"""Тесты для SourceClassifier."""

import pytest

from src.bp1.adaptive.schemas import SourceType, StrategyType
from src.bp1.adaptive.strategies.classifier import SourceClassifier

from .constants import (
    CLASSIFIER_ANTIBOT_HEADERS,
    CLASSIFIER_API_NAME,
    CLASSIFIER_API_URL,
    CLASSIFIER_CAPTCHA_HTML,
    CLASSIFIER_COMPLEXITY_THRESHOLD,
    CLASSIFIER_NEWS_NAME,
    CLASSIFIER_NEWS_URL,
    CLASSIFIER_REGISTRY_NAME,
    CLASSIFIER_REGISTRY_URL,
    CLASSIFIER_SIMPLE_NAME,
    CLASSIFIER_SIMPLE_URL,
    CLASSIFIER_SPA_HTML,
)


@pytest.mark.asyncio
async def test_classify_api_source():
    """API-источник классифицируется как API."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name=CLASSIFIER_API_NAME,
        source_url=CLASSIFIER_API_URL,
    )
    assert result.source_type == SourceType.API
    assert result.recommended_strategy == StrategyType.FAST.value


@pytest.mark.asyncio
async def test_classify_registry_source():
    """Реестровый источник классифицируется как REGISTRY."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name=CLASSIFIER_REGISTRY_NAME,
        source_url=CLASSIFIER_REGISTRY_URL,
    )
    assert result.source_type == SourceType.REGISTRY


@pytest.mark.asyncio
async def test_classify_news_source():
    """Новостной источник классифицируется как NEWS."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name=CLASSIFIER_NEWS_NAME,
        source_url=CLASSIFIER_NEWS_URL,
    )
    assert result.source_type == SourceType.NEWS


@pytest.mark.asyncio
async def test_classify_captcha_leads_to_hitl():
    """Наличие CAPTCHA приводит к стратегии HITL."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name=CLASSIFIER_SIMPLE_NAME,
        source_url=CLASSIFIER_SIMPLE_URL,
        html=CLASSIFIER_CAPTCHA_HTML,
    )
    assert result.has_captcha is True
    assert result.recommended_strategy == StrategyType.HITL.value


@pytest.mark.asyncio
async def test_classify_antibot_leads_to_stealth():
    """Наличие антибот-защиты приводит к стратегии STEALTH."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name=CLASSIFIER_SIMPLE_NAME,
        source_url=CLASSIFIER_SIMPLE_URL,
        headers=CLASSIFIER_ANTIBOT_HEADERS,
    )
    assert result.has_antibot is True
    assert result.recommended_strategy == StrategyType.STEALTH.value


@pytest.mark.asyncio
async def test_classify_spa_leads_to_browser():
    """SPA-приложение классифицируется как SPA и приводит к BROWSER."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name=CLASSIFIER_SIMPLE_NAME,
        source_url=CLASSIFIER_SIMPLE_URL,
        html=CLASSIFIER_SPA_HTML,
    )
    assert result.is_spa is True
    assert result.source_type == SourceType.SPA
    assert result.recommended_strategy == StrategyType.BROWSER.value


@pytest.mark.asyncio
async def test_classify_simple_leads_to_fast():
    """Простой источник приводит к стратегии FAST."""
    classifier = SourceClassifier()
    result = await classifier.classify(
        source_name=CLASSIFIER_SIMPLE_NAME,
        source_url=CLASSIFIER_SIMPLE_URL,
    )
    assert result.recommended_strategy == StrategyType.FAST.value
    assert result.complexity_score < CLASSIFIER_COMPLEXITY_THRESHOLD
