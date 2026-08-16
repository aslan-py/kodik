"""Мапперы ответов LLM в доменные Pydantic-схемы (BP-1 Adaptive).

Преобразуют типизированные ответы LLM (``_llm.schemas``) в доменные
модели ``AdapterConfig``, ``ExtendedSiteClassification``. Логика вынесена
из ``llm.py``, чтобы классы-фасады оставались тонкими.
"""

from __future__ import annotations

from typing import Any

from ...schemas import (
    AdapterConfig,
    BusinessFeatures,
    ExtendedSiteClassification,
    PageSubType,
    SiteType,
    TechnicalFeatures,
)
from .schemas import (
    ClassificationResponse,
    EnrichmentResponse,
    RelevanceResponse,
    SelectorExtractionResponse,
)


def to_adapter_config(
    data: SelectorExtractionResponse,
    expected_fields: list[str],
) -> AdapterConfig:
    """Формирует AdapterConfig из типизированного ответа анализа."""
    selectors = data.selectors
    schema = data.schema_

    # Нормализация селекторов: только строковые значения.
    selectors = {
        k: (v if isinstance(v, str) else '') for k, v in selectors.items()
    }

    # Если схема пустая — заполняем из ожидаемых полей.
    if not schema:
        schema = dict.fromkeys(expected_fields, 'string')

    return AdapterConfig(
        source_name='adaptive',
        base_url='',
        expected_schema=schema,
        selectors=selectors,
        confidence=data.confidence,
        adaptive=True,
        auto_save=True,
    )


def to_extended_classification(
    data: ClassificationResponse,
    url: str,
    headers: dict[str, Any],
) -> ExtendedSiteClassification:
    """Формирует ExtendedSiteClassification из типизированного ответа."""
    site_type_raw = (data.site_type or 'other').lower()
    try:
        site_type = SiteType(site_type_raw)
    except ValueError:
        site_type = SiteType.OTHER

    page_raw = (data.page_subtype or 'other').lower()
    try:
        page_subtype = PageSubType(page_raw)
    except ValueError:
        page_subtype = PageSubType.OTHER

    technical_data = data.technical_features or {}
    technical = TechnicalFeatures(
        frameworks=technical_data.get('frameworks') or [],
        css_frameworks=technical_data.get('css_frameworks') or [],
        has_antibot=bool(technical_data.get('has_antibot', False)),
        has_captcha=bool(technical_data.get('has_captcha', False)),
        is_spa=bool(technical_data.get('is_spa', False)),
        has_mobile_version=bool(
            technical_data.get('has_mobile_version', False)
        ),
    )

    business_data = data.business_features or {}
    business_features = BusinessFeatures(
        **{
            k: bool(v)
            for k, v in business_data.items()
            if k in BusinessFeatures.model_fields
        }
    )

    return ExtendedSiteClassification(
        source_name=url,
        site_type=site_type,
        page_subtype=page_subtype,
        confidence=data.confidence,
        business_features=business_features,
        technical_features=technical,
        complexity_score=data.complexity_score,
        recommended_strategy=data.recommended_strategy,
        metadata={
            'title': (
                data.metadata.get('title', '')
                if isinstance(data.metadata, dict)
                else ''
            ),
            'url': url,
            'headers_detected': bool(headers),
        },
    )


def to_relevance_scores(
    raw_items: list[dict[str, Any]],
    response: RelevanceResponse,
) -> list[dict[str, Any]]:
    """Связывает оценки LLM с исходными элементами.

    Сопоставляет ``response.items`` (по ``index``) с элементами списка
    ``raw_items``. Для отсутствующих индексов используется нейтральная
    оценка ``0.5`` (нерелевантно), чтобы фильтр никогда не падал на
    неполном ответе модели.

    Args:
        raw_items: Собранные элементы ``(title, url, text)``.
        response: Типизированный ответ пакетного скоринга.

    Returns:
        Список словарей ``{"index", "score", "relevant"}`` той же длины,
        что и ``raw_items``.
    """
    by_index = {item.index: item for item in response.items}
    result: list[dict[str, Any]] = []
    for i, _raw in enumerate(raw_items):
        entry = by_index.get(i)
        if entry is not None:
            result.append(
                {
                    'index': entry.index,
                    'score': round(entry.score, 3),
                    'relevant': entry.relevant,
                }
            )
        else:
            result.append({'index': i, 'score': 0.5, 'relevant': False})
    return result


def to_enrichment(data: EnrichmentResponse) -> dict[str, Any]:
    """Преобразует типизированный ответ обогащения в плоский словарь.

    Возвращает только заполненные поля (``None``/пустые значения
    отбрасываются), чтобы в ``extra.news[]`` не попадал лишний мусор.
    """
    result: dict[str, Any] = {}
    if data.published_at:
        result['published_at'] = data.published_at
    if data.author:
        result['author'] = data.author
    if data.keywords:
        result['keywords'] = data.keywords[:20]
    if data.summary:
        result['summary'] = data.summary
    if data.mentioned_company:
        result['mentioned_company'] = data.mentioned_company
    if data.mentioned_inn:
        result['mentioned_inn'] = data.mentioned_inn
    if data.sentiment:
        result['sentiment'] = data.sentiment
    return result
