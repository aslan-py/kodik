"""
Адаптивный сбор данных (BP-1 Adaptive).

Интеллектуальная система сбора данных, которая автоматически определяет
структуру сайта, извлекает данные без предварительной настройки и
адаптируется к изменениям в реальном времени.

Пакет организован по слоям:

- ``core`` — инфраструктура (кэширование, контроль качества).
- ``processing`` — обработка HTML и извлечение данных (парсер, LLM).
- ``strategies`` — стратегии обхода источников.
- ``integration`` — интеграция с BP-1 и внешними интерфейсами (MCP, CLI).
"""

from .core.cache import UnifiedCache
from .core.quality import DataQualityGate
from .integration.bridge import AdaptiveBridgeParser
from .integration.mcp_server import MCPServer, run_mcp_server
from .integration.runner import AdaptiveRunner
from .logger import get_logger
from .processing.llm import AIAgent, LLMClient
from .processing.parser import AdaptiveParser
from .schemas import (
    AdapterConfig,
    AdapterState,
    AdaptiveParseResult,
    HITLRequest,
    HITLResponse,
    PipelineReport,
    QualityGateLevel,
    QualityGateReport,
    QuarantineRecord,
    SourceClassification,
    SourceRegistrationResult,
    SourceType,
    StrategyResult,
    StrategyType,
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
    'Crawl4AIStrategy',
    'DataQualityGate',
    'HITLManager',
    'HITLRequest',
    'HITLResponse',
    'HITLStrategy',
    'LLMClient',
    'MCPServer',
    'PipelineReport',
    'ProfileManager',
    'QualityGateLevel',
    'QualityGateReport',
    'QuarantineRecord',
    'SourceClassification',
    'SourceClassifier',
    'SourceRegistrationResult',
    'SourceType',
    'StealthStrategy',
    'StrategyResult',
    'StrategyType',
    'UnifiedCache',
    'UnifiedConfig',
    'get_logger',
    'run_mcp_server',
]
