"""
Pydantic-схемы адаптивного сбора данных (BP-1 Adaptive).

Определяют модели данных для классификации источников, стратегий обхода,
адаптеров, контроля качества, HITL и отчётов пайплайна.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Текущее время в UTC (timezone-aware)."""
    return datetime.now(UTC)


# ============================================================================
# КЛАССИФИКАЦИЯ ИСТОЧНИКА
# ============================================================================


class SourceType(StrEnum):
    """Тип источника данных."""

    NEWS = 'news'
    REGISTRY = 'registry'
    API = 'api'
    SPA = 'spa'
    UNKNOWN = 'unknown'


class SourceClassification(BaseModel):
    """Результат классификации источника."""

    source_name: str
    source_type: SourceType = SourceType.UNKNOWN
    complexity_score: float = Field(0.0, ge=0.0, le=1.0)
    has_antibot: bool = False
    has_captcha: bool = False
    is_spa: bool = False
    recommended_strategy: str = 'FAST'


# ============================================================================
# СТРАТЕГИИ ОБХОДА
# ============================================================================


class StrategyType(StrEnum):
    """Типы стратегий обхода."""

    FAST = 'FAST'
    CRAWL4AI = 'CRAWL4AI'
    BROWSER = 'BROWSER'
    WAYBACK = 'WAYBACK'
    STEALTH = 'STEALTH'
    HITL = 'HITL'


class StrategyResult(BaseModel):
    """Результат выполнения стратегии."""

    strategy: StrategyType
    success: bool = False
    data: str | None = None
    content_length: int = 0
    error: str | None = None
    elapsed_ms: int = 0
    used_cache: bool = False


# ============================================================================
# АДАПТЕРЫ
# ============================================================================


class AdapterConfig(BaseModel):
    """Конфигурация адаптера для источника."""

    source_name: str
    base_url: str
    adaptive: bool = True
    auto_save: bool = True
    min_text_length: int = 300
    timeout_ms: int = 60000
    expected_schema: dict[str, Any] = Field(default_factory=dict)
    selectors: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class AdapterState(BaseModel):
    """Состояние адаптера в кэше."""

    source_name: str
    selectors: dict[str, str] = Field(default_factory=dict)
    schema_config: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    version: int = 1
    created_at: datetime = Field(default_factory=_utcnow)
    last_used_at: datetime = Field(default_factory=_utcnow)
    fail_count: int = 0


class AdaptiveParseResult(BaseModel):
    """Результат адаптивного парсинга."""

    status: str = 'ok'
    source_name: str
    url: str
    strategy_used: StrategyType = StrategyType.FAST
    items: list[dict[str, Any]] = Field(default_factory=list)
    raw_text: str | None = None
    error: str | None = None
    adapter_version: int | None = None
    elapsed_ms: int = 0
    trace_id: str | None = None


class SourceRegistrationResult(BaseModel):
    """Результат регистрации нового источника.

    host — hostname (для Redis-ключа классификации), source_name — полный
    URL (как хранится в Source.name), classification — результат
    SourceClassifier.
    """

    host: str
    source_name: str
    created: bool
    source_id: int | None = None
    classification: SourceClassification


# ============================================================================
# КОНТРОЛЬ КАЧЕСТВА
# ============================================================================


class QualityGateLevel(StrEnum):
    """Уровни валидации качества."""

    SCHEMA = 'SCHEMA'
    TYPES = 'TYPES'
    BUSINESS = 'BUSINESS'
    VOLUME = 'VOLUME'
    CONSISTENCY = 'CONSISTENCY'


class QualityGateReport(BaseModel):
    """Отчёт одного уровня Quality Gate."""

    level: QualityGateLevel
    passed: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    item_count: int = 0
    passed_count: int = 0
    quarantined_count: int = 0


class QuarantineRecord(BaseModel):
    """Запись карантина для проблемных данных."""

    id: str
    original_data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)
    source: str = 'unknown'
    created_at: datetime = Field(default_factory=_utcnow)
    resolved: bool = False


# ============================================================================
# HITL (HUMAN-IN-THE-LOOP)
# ============================================================================


class HITLRequest(BaseModel):
    """Запрос на участие человека."""

    request_id: str
    url: str
    challenge_type: str = 'captcha'
    profile_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    status: str = 'pending'


class HITLResponse(BaseModel):
    """Ответ от человека."""

    request_id: str
    success: bool = False
    profile_id: str | None = None
    cookies: dict[str, Any] = Field(default_factory=dict)
    html: str | None = None
    error: str | None = None


# ============================================================================
# MCP-ИНСТРУМЕНТЫ
# ============================================================================


class MCPTool(BaseModel):
    """Описание инструмента MCP-сервера."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# КОНФИГУРАЦИЯ И ОТЧЁТЫ
# ============================================================================


class UnifiedConfig(BaseModel):
    """Единая конфигурация адаптивного пайплайна."""

    mode: str = 'adaptive'
    headless: bool = True
    timeout: int = 60000
    adaptive_config: AdapterConfig | None = None
    quality_gate_enabled: bool = True
    cache_profiles: bool = True
    max_concurrent: int = 5


class PipelineStage(BaseModel):
    """Результат одной стадии пайплайна."""

    name: str
    status: str = 'ok'
    duration_ms: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class PipelineReport(BaseModel):
    """Отчёт пайплайна."""

    pipeline_id: str
    mode: str = 'adaptive'
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    total_duration_ms: int = 0
    stages: list[PipelineStage] = Field(default_factory=list)
    overall_status: str = 'ok'
