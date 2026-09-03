"""
Pydantic-схемы адаптивного сбора данных (BP-1 Adaptive).

Определяют модели данных для классификации источников, стратегий обхода,
адаптеров, контроля качества, HITL и отчётов пайплайна.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

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


class SiteType(StrEnum):
    """Детализированный тип сайта.

    Расширяет ``SourceType`` более узкой классификацией контента сайта
    (магазин, доска объявлений, агрегатор отзывов и т.д.). Используется
    совместно с ``SourceType``: ``SourceType`` определяет способ обхода,
    ``SiteType`` — бизнес-направление.
    """

    NEWS = 'news'
    JOB_BOARD = 'job_board'
    MARKETPLACE = 'marketplace'
    CATALOG = 'catalog'
    E_COMMERCE = 'e_commerce'
    CLASSIFIEDS = 'classifieds'
    REVIEW_AGGREGATOR = 'review_aggregator'
    QUESTION_ANSWER = 'question_answer'
    WIKI = 'wiki'
    EDUCATION = 'education'
    FINANCE = 'finance'
    REAL_ESTATE = 'real_estate'
    LEGAL = 'legal'
    MEDIA = 'media'
    FORUM = 'forum'
    SOCIAL = 'social'
    GOVERNMENT = 'government'
    BLOG = 'blog'
    DOCUMENTATION = 'documentation'
    OTHER = 'other'


class PageSubType(StrEnum):
    """Подтип страницы внутри сайта."""

    # Общие
    HOME = 'home'
    SEARCH = 'search'
    LIST = 'list'
    DETAIL = 'detail'
    CATEGORY = 'category'
    PROFILE = 'profile'
    ARCHIVE = 'archive'
    CART = 'cart'
    CHECKOUT = 'checkout'
    LOGIN = 'login'
    REGISTER = 'register'
    ABOUT = 'about'
    CONTACT = 'contact'
    OTHER = 'other'

    # Новости
    NEWS_MAIN = 'news_main'
    NEWS_CATEGORY = 'news_category'
    NEWS_ARTICLE = 'news_article'
    NEWS_ARCHIVE = 'news_archive'
    NEWS_SEARCH = 'news_search'

    # Вакансии
    JOB_MAIN = 'job_main'
    JOB_VACANCY = 'job_vacancy'
    JOB_SEARCH = 'job_search'
    JOB_COMPANY = 'job_company'
    JOB_RESUME = 'job_resume'

    # Маркетплейсы
    MARKETPLACE_MAIN = 'marketplace_main'
    MARKETPLACE_CATEGORY = 'marketplace_category'
    MARKETPLACE_PRODUCT = 'marketplace_product'
    MARKETPLACE_SEARCH = 'marketplace_search'
    MARKETPLACE_CART = 'marketplace_cart'

    # Госреестры
    REGISTRY_MAIN = 'registry_main'
    REGISTRY_SEARCH = 'registry_search'
    REGISTRY_RESULT = 'registry_result'
    REGISTRY_DETAIL = 'registry_detail'


class BusinessFeatures(BaseModel):
    """Бизнес-характеристики сайта."""

    has_payment: bool = False
    has_delivery: bool = False
    has_reviews: bool = False
    has_rating: bool = False
    has_user_accounts: bool = False
    has_cart: bool = False
    has_search: bool = False
    has_filters: bool = False
    has_pagination: bool = False
    has_comments: bool = False
    has_sharing: bool = False


class TechnicalFeatures(BaseModel):
    """Технические характеристики сайта."""

    frameworks: list[str] = Field(default_factory=list)
    css_frameworks: list[str] = Field(default_factory=list)
    has_antibot: bool = False
    has_captcha: bool = False
    is_spa: bool = False
    has_mobile_version: bool = False


class SourceClassification(BaseModel):
    """Результат классификации источника."""

    source_name: str
    source_type: SourceType = SourceType.UNKNOWN
    complexity_score: float = Field(0.0, ge=0.0, le=1.0)
    has_antibot: bool = False
    has_captcha: bool = False
    is_spa: bool = False
    recommended_strategy: str = 'FAST'


class ExtendedSiteClassification(BaseModel):
    """Расширенная классификация сайта.

    Дополняет ``SourceClassification`` бизнес- и техническими характеристиками,
    подтипом страницы и детализированным типом сайта. Используется
    расширенной классификацией (``SourceClassifier.classify_extended``
    и ``LLMClient.classify_with_llm``).
    """

    source_name: str
    site_type: SiteType = SiteType.OTHER
    page_subtype: PageSubType = PageSubType.OTHER
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    business_features: BusinessFeatures = Field(
        default_factory=BusinessFeatures
    )
    technical_features: TechnicalFeatures = Field(
        default_factory=TechnicalFeatures
    )
    complexity_score: float = Field(0.0, ge=0.0, le=1.0)
    recommended_strategy: str = 'FAST'
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_source_classification(self) -> SourceClassification:
        """Конвертирует в базовую ``SourceClassification``.

        Обеспечивает обратную совместимость с кодом, работающим с
        ``SourceClassification``.
        """
        return SourceClassification(
            source_name=self.source_name,
            source_type=SourceType.UNKNOWN,
            complexity_score=self.complexity_score,
            has_antibot=self.technical_features.has_antibot,
            has_captcha=self.technical_features.has_captcha,
            is_spa=self.technical_features.is_spa,
            recommended_strategy=self.recommended_strategy,
        )


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
    # Материалы получены через RSS/Atom-фид или sitemap.xml — ранний выход
    # из AdaptiveParser.parse() до HTML-лестницы (design.md изменения
    # add-rss-sitemap-collection, D4). Не участвует в _DEGRADATION_ORDER
    # AgenticOrchestrator — используется только для наблюдаемости
    # (metrics.strategy_used, «по факту», Шаг 20 плана рефакторинга).
    FEED = 'FEED'


class StrategyResult(BaseModel):
    """Результат выполнения стратегии."""

    strategy: StrategyType
    success: bool = False
    data: str | None = None
    content_length: int = 0
    error: str | None = None
    elapsed_ms: int = 0
    used_cache: bool = False
    # HTTP-статус ответа целевого источника, если доступен (RPA-стратегии
    # с браузером/краулером). Используется оркестратором для решения о
    # cooldown прокси, заблокированного источником (401/403/429) — см.
    # openspec/changes/add-rpa-collection-proxying.
    http_status: int | None = None


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
    # Результат проверки поискового эндпоинта при регистрации (Шаг 19
    # плана рефакторинга): None — проверка не выполнялась или эндпоинт не
    # ответил. Заполняется, когда register() вызван с probe_search=True.
    search_probe: ProbedUrl | None = None


class FeedDiscovery(BaseModel):
    """Результат обнаружения RSS/Atom/sitemap на источнике (кэш
    обнаружения, design.md изменения add-rss-sitemap-collection, D5).

    ``feed_url=None`` — явная отметка «обнаружение выполнялось, фида нет»
    (отличается от отсутствия записи в кэше: отсутствие записи означает
    «обнаружение ещё не выполнялось»).
    """

    source_name: str
    feed_url: str | None = None
    kind: Literal['rss', 'sitemap'] | None = None
    fail_count: int = 0


class ProbedUrl(BaseModel):
    """Результат пробинга поискового URL (SearchUrlProber).

    Описывает найденный в ходе пробинга поисковый URL источника в форме,
    пригодной для повторного использования без повторного пробинга: кэшируется
    в Redis (TTL 7 дней).
    """

    source_name: str
    search_url: str
    search_method: Literal['GET', 'POST'] = 'GET'
    search_params: dict[str, str] = Field(default_factory=dict)
    result_count_selector: str | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    probed_at: datetime = Field(default_factory=_utcnow)


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


class RelevanceMode(StrEnum):
    """Режим фильтрации релевантности (Фича 1)."""

    OFF = 'off'
    FILTER = 'filter'
    RANK = 'rank'


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
