"""Pydantic-модели ответов LLM (BP-1 Adaptive).

Определяют типизированные структуры ответов, которые возвращает модель
для каждой задачи: извлечение селекторов, классификация сайта, выбор
стратегии и анализ результата. Валидация, дефолты и нормализация
выполняются автоматически, а мапперы становятся тонкими.

Примечание: поле ``schema`` в ``SelectorExtractionResponse`` использует
``alias='schema'`` и ``populate_by_name=True``, чтобы не конфликтовать
с атрибутом ``BaseModel.schema`` (Pydantic v2).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SelectorExtractionResponse(BaseModel):
    """Ответ LLM на извлечение CSS-селекторов и схемы данных.

    Используется как для полного анализа страницы, так и для анализа
    отдельного чанка. Поля необязательны — модель может не заполнить
    часть из них, особенно при анализе фрагмента.
    """

    model_config = ConfigDict(populate_by_name=True)

    selectors: dict[str, Any] = Field(default_factory=dict)
    schema_: dict[str, Any] = Field(
        default_factory=dict, alias='schema', validation_alias='schema'
    )
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationResponse(BaseModel):
    """Ответ LLM на детальную классификацию сайта."""

    site_type: str = 'other'
    page_subtype: str = 'other'
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    business_features: dict[str, Any] = Field(default_factory=dict)
    technical_features: dict[str, Any] = Field(default_factory=dict)
    complexity_score: float = Field(0.0, ge=0.0, le=1.0)
    recommended_strategy: str = 'FAST'
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategyResponse(BaseModel):
    """Ответ LLM на выбор стратегии обхода."""

    strategy: str = ''


class ResultAnalysisResponse(BaseModel):
    """Ответ LLM на анализ результата парсинга."""

    recommendation: str = ''
    confidence: float = Field(0.0, ge=0.0, le=1.0)
