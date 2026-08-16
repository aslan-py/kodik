"""
Адаптивный сбор данных (BP-1 Adaptive).

Интеллектуальная система сбора данных, которая автоматически определяет
структуру сайта, извлекает данные без предварительной настройки и
адаптируется к изменениям в реальном времени.

Пакет организован по слоям:

- ``core`` — инфраструктура (кэширование, контроль качества).
- ``processing`` — обработка HTML и извлечение данных (парсер, LLM).
- ``strategies`` — стратегии обхода источников.
- ``integration`` — интеграция с BP-1 и внешними интерфейсами (CLI).
"""

from .core.cache import UnifiedCache
from .core.quality import DataQualityGate
from .integration.bridge import AdaptiveBridgeParser
from .integration.runner import AdaptiveRunner
from .logger import get_logger
from .processing.llm import AIAgent, LLMClient
from .processing.parser import AdaptiveParser
from .processing.relevance import RelevanceFilter
from .schemas import (
    AdapterConfig,
    AdapterState,
    AdaptiveParseResult,
    BusinessFeatures,
    ExtendedSiteClassification,
    HITLRequest,
    HITLResponse,
    PageSubType,
    PipelineReport,
    QualityGateLevel,
    QualityGateReport,
    QuarantineRecord,
    RelevanceMode,
    SiteType,
    SourceClassification,
    SourceRegistrationResult,
    SourceType,
    StrategyResult,
    StrategyType,
    TechnicalFeatures,
    UnifiedConfig,
)
from .strategies.classifier import SourceClassifier
from .strategies.engines import (
    Crawl4AIStrategy,
    HITLStrategy,
    StealthStrategy,
)
from .strategies.hitl import HITLManager, ProfileManager
from .strategies.orchestrator import AgenticOrchestrator

__all__ = [
    'AIAgent',
    'AdapterConfig',
    'AdapterState',
    'AdaptiveBridgeParser',
    'AdaptiveParseResult',
    'AdaptiveParser',
    'AdaptiveRunner',
    'AgenticOrchestrator',
    'BusinessFeatures',
    'Crawl4AIStrategy',
    'DataQualityGate',
    'ExtendedSiteClassification',
    'HITLManager',
    'HITLRequest',
    'HITLResponse',
    'HITLStrategy',
    'LLMClient',
    'PageSubType',
    'PipelineReport',
    'ProfileManager',
    'QualityGateLevel',
    'QualityGateReport',
    'QuarantineRecord',
    'RelevanceFilter',
    'RelevanceMode',
    'SiteType',
    'SourceClassification',
    'SourceClassifier',
    'SourceRegistrationResult',
    'SourceType',
    'StealthStrategy',
    'StrategyResult',
    'StrategyType',
    'TechnicalFeatures',
    'UnifiedCache',
    'UnifiedConfig',
    'get_logger',
]
