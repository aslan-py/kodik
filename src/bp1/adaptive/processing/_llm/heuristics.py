"""Эвристические fallback-реализации (BP-1 Adaptive).

Используются, когда LLM не настроен или недоступен: классификация по
HTML-разметке, анализ структуры по ссылкам и выбор стратегии по
классификации источника. Логика вынесена из ``llm.py``.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...schemas import (
    AdapterConfig,
    ExtendedSiteClassification,
    SiteType,
    SourceClassification,
    StrategyType,
    TechnicalFeatures,
)
from . import constants


def heuristic_analyze(
    html: str,
    expected_fields: list[str],
) -> AdapterConfig:
    """Эвристический fallback-анализ структуры.

    Возвращает схему из ожидаемых полей и пустые селекторы (кроме
    ``url`` — ``a[href]``), чтобы парсер мог использовать эвристику
    по ссылкам.
    """
    return AdapterConfig(
        source_name='adaptive',
        base_url='',
        expected_schema=dict.fromkeys(expected_fields, 'string'),
        selectors={'url': 'a[href]'},
        adaptive=True,
        auto_save=True,
    )


def heuristic_classify(
    html: str,
    url: str,
) -> ExtendedSiteClassification:
    """Эвристическая классификация (fallback без LLM)."""
    soup = BeautifulSoup(html, 'html.parser')

    site_type = SiteType.OTHER
    for item in soup.find_all(attrs={'itemtype': re.compile(r'schema\.org')}):
        item_str = str(item).lower()
        if 'product' in item_str:
            site_type = SiteType.E_COMMERCE
        elif 'jobposting' in item_str:
            site_type = SiteType.JOB_BOARD
        elif 'article' in item_str:
            site_type = SiteType.NEWS
            break

    if site_type == SiteType.OTHER and any(
        soup.select_one(sel)
        for sel in ('.cart', '#cart', '.basket', '.shopping-cart')
    ):
        site_type = SiteType.E_COMMERCE

    technical = TechnicalFeatures(
        is_spa='id="app"' in html or 'id="root"' in html,
        has_antibot='cloudflare' in html.lower(),
    )

    confidence = (
        constants.DEFAULT_SITE_CONFIDENCE
        if site_type != SiteType.OTHER
        else constants.UNKNOWN_SITE_CONFIDENCE
    )

    return ExtendedSiteClassification(
        source_name=url,
        site_type=site_type,
        confidence=confidence,
        technical_features=technical,
        metadata={'url': url, 'heuristic': True},
    )


def heuristic_strategy(classification: SourceClassification) -> StrategyType:
    """Эвристический выбор стратегии по классификации."""
    if classification.has_captcha or classification.has_antibot:
        return StrategyType.STEALTH
    if classification.is_spa:
        return StrategyType.BROWSER
    return StrategyType.FAST
