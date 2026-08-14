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


def heuristic_relevance_score(
    text: str,
    competitor: str,
    trigger: str = '',
    inn: str | None = None,
) -> float:
    """Лексический скоринг релевантности текста (fallback без LLM).

    Детерминированная оценка ``0.0-1.0`` по совпадению токенов названия
    конкурента, ИНН и темы поиска в ``text``/``title``.

    - Точное вхождение полного названия или ИНН → максимальный балл.
    - Совпадение значимых токенов названия (без стоп-слов) → частичный балл.
    - Совпадение токенов темы → небольшой бонус.

    Args:
        text: Текст/заголовок элемента, по которому оцениваем.
        competitor: Название конкурента.
        trigger: Тема поиска (опционально).
        inn: ИНН конкурента (опционально).

    Returns:
        float: оценка ``0.0-1.0``.
    """
    text_l = (text or '').lower()
    comp_l = (competitor or '').lower().strip()
    trig_l = (trigger or '').lower().strip()

    if not text_l or not comp_l:
        return 0.0

    # Полное вхождение названия конкурента или ИНН — максимально релевантно.
    if comp_l and comp_l in text_l:
        return 1.0
    if inn and str(inn) in text_l:
        return 1.0

    # Значимые токены названия (длина > 3, без стоп-слов и орг. форм).
    stop = {
        'ооо',
        'зао',
        'оао',
        'пао',
        'ао',
        'ип',
        'ии',
        'оооо',
        'архитект',
        'архитех',
    }
    tokens = [
        t
        for t in re.findall(r'[а-яёa-z0-9]+', comp_l)
        if len(t) > 3 and t not in stop
    ]
    if tokens:
        matches = sum(1 for t in tokens if t in text_l)
        base = matches / len(tokens)
    else:
        base = 0.0

    score = base * 0.9

    # Бонус за совпадение темы поиска.
    if trig_l and len(trig_l) > 2 and trig_l in text_l:
        score += 0.1

    return max(0.0, min(1.0, score))
