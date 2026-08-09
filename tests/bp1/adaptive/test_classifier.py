"""Тесты для SourceClassifier."""

import pytest

from src.bp1.adaptive.schemas import SiteType, SourceType, StrategyType
from src.bp1.adaptive.strategies.classifier import SourceClassifier

from .constants import (
    CLASSIFIER_ANGULAR_HTML,
    CLASSIFIER_ANTIBOT_HEADERS,
    CLASSIFIER_API_NAME,
    CLASSIFIER_API_URL,
    CLASSIFIER_BOOTSTRAP_HTML,
    CLASSIFIER_CAPTCHA_HTML,
    CLASSIFIER_CART_HTML,
    CLASSIFIER_COMPLEXITY_THRESHOLD,
    CLASSIFIER_E_COMMERCE_HTML,
    CLASSIFIER_JOB_HTML,
    CLASSIFIER_JOB_PAGE_HTML,
    CLASSIFIER_METRIKA_HTML,
    CLASSIFIER_NEWS_NAME,
    CLASSIFIER_NEWS_URL,
    CLASSIFIER_REACT_HTML,
    CLASSIFIER_REGISTRY_NAME,
    CLASSIFIER_REGISTRY_URL,
    CLASSIFIER_SIMPLE_NAME,
    CLASSIFIER_SIMPLE_URL,
    CLASSIFIER_SPA_HTML,
    CLASSIFIER_TAILWIND_HTML,
    CLASSIFIER_VUE_HTML,
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


# ============================================================================
# Расширенные детекторы
# ============================================================================


def test_detect_site_type_e_commerce():
    """schema.org Product / og:type=product определяет e-commerce."""
    classifier = SourceClassifier()
    assert (
        classifier._detect_site_type(CLASSIFIER_E_COMMERCE_HTML)
        == SiteType.E_COMMERCE
    )
    assert (
        classifier._detect_site_type(CLASSIFIER_CART_HTML)
        == SiteType.E_COMMERCE
    )


def test_detect_site_type_job_board():
    """schema.org JobPosting определяет job_board."""
    classifier = SourceClassifier()
    assert (
        classifier._detect_site_type(CLASSIFIER_JOB_HTML) == SiteType.JOB_BOARD
    )


def test_detect_site_type_other():
    """Пустой/неизвестный HTML даёт SiteType.OTHER."""
    classifier = SourceClassifier()
    assert classifier._detect_site_type('') == SiteType.OTHER
    assert classifier._detect_site_type('<html><body>hi</body></html>') == (
        SiteType.OTHER
    )


def test_detect_js_frameworks():
    """Детекция JS-фреймворков по маркерам."""
    classifier = SourceClassifier()
    assert classifier._detect_js_frameworks(CLASSIFIER_REACT_HTML) == ['react']
    assert classifier._detect_js_frameworks(CLASSIFIER_VUE_HTML) == ['vue']
    assert classifier._detect_js_frameworks(CLASSIFIER_ANGULAR_HTML) == [
        'angular'
    ]
    assert classifier._detect_js_frameworks('<html></html>') == []


def test_detect_css_patterns():
    """Детекция CSS-фреймворков по маркерам."""
    classifier = SourceClassifier()
    assert classifier._detect_css_patterns(CLASSIFIER_BOOTSTRAP_HTML) == [
        'bootstrap'
    ]
    assert classifier._detect_css_patterns(CLASSIFIER_TAILWIND_HTML) == [
        'tailwind'
    ]
    assert classifier._detect_css_patterns('<html></html>') == []


def test_detect_meta():
    """Детекция метрик в HTML."""
    classifier = SourceClassifier()
    meta = classifier._detect_meta(CLASSIFIER_METRIKA_HTML)
    assert meta['has_ya_metrika'] is True


@pytest.mark.asyncio
async def test_classify_extended_returns_extra_fields():
    """classify_extended возвращает детализированный тип сайта."""
    classifier = SourceClassifier()
    result = await classifier.classify_extended(
        source_name=CLASSIFIER_SIMPLE_NAME,
        source_url=CLASSIFIER_SIMPLE_URL,
        html=CLASSIFIER_JOB_PAGE_HTML,
    )
    assert result.source_name == CLASSIFIER_SIMPLE_NAME
    assert result.recommended_strategy in {
        StrategyType.FAST.value,
        StrategyType.BROWSER.value,
    }
    assert result.complexity_score >= 0.0
    # На странице есть пагинация и поиск не присутствует.
    assert result.business_features.has_pagination is True


@pytest.mark.asyncio
async def test_classify_extended_e_commerce_site_type():
    """classify_extended распознаёт e-commerce по schema.org."""
    classifier = SourceClassifier()
    result = await classifier.classify_extended(
        source_name=CLASSIFIER_SIMPLE_NAME,
        source_url=CLASSIFIER_SIMPLE_URL,
        html=CLASSIFIER_E_COMMERCE_HTML,
    )
    assert result.site_type == SiteType.E_COMMERCE
