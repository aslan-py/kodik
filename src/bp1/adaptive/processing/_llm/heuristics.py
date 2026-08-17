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
    SourceType,
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


def heuristic_strategy(
    classification: SourceClassification,
    *,
    escalate_captcha_to_hitl: bool = False,
) -> StrategyType:
    """Эвристический выбор стратегии по классификации источника.

    Единая реализация для ``SourceClassifier._pick_strategy`` (первичная
    категоризация источника) и ``AIAgent`` (фолбэк, когда LLM недоступен) —
    раньше эти два места дублировали почти одинаковую, но расходящуюся
    логику по отдельности.

    Приоритет: API-источник -> FAST, CAPTCHA -> HITL/STEALTH (см.
    ``escalate_captcha_to_hitl``), антибот-защита -> STEALTH,
    SPA-приложение -> BROWSER, иначе -> FAST.

    Args:
        classification: Классификация источника.
        escalate_captcha_to_hitl: При CAPTCHA сразу рекомендовать HITL
            вместо STEALTH. Включено у ``SourceClassifier`` (HITL —
            обоснованная стартовая точка деградации для источника с уже
            известной CAPTCHA). Выключено по умолчанию — таким было
            поведение ``AIAgent``-фолбэка до объединения, и он намеренно
            не эскалирует к участию человека без реального решения LLM
            (см. ``test_agent_choose_strategy_heuristic_captcha``).
    """
    if classification.source_type == SourceType.API:
        return StrategyType.FAST
    if classification.has_captcha:
        return (
            StrategyType.HITL
            if escalate_captcha_to_hitl
            else StrategyType.STEALTH
        )
    if classification.has_antibot:
        return StrategyType.STEALTH
    if classification.is_spa:
        return StrategyType.BROWSER
    return StrategyType.FAST
