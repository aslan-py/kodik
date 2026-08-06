"""
Адаптивный сбор данных (BP-1 Adaptive).

Интеллектуальная система сбора данных, которая автоматически определяет
структуру сайта, извлекает данные без предварительной настройки и
адаптируется к изменениям в реальном времени.
"""

from .bridge import AdaptiveBridgeParser
from .cache import UnifiedCache
from .classifier import SourceClassifier
from .engines import (
    Crawl4AIStrategy,
    HITLStrategy,
    StealthStrategy,
)
from .hitl import HITLManager, ProfileManager
from .llm import AIAgent, LLMClient
from .logger import get_logger
from .mcp_server import MCPServer, run_mcp_server
from .orchestrator import AgenticOrchestrator
from .parser import AdaptiveParser
from .quality import DataQualityGate
from .runner import AdaptiveRunner
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
    SourceType,
    StrategyResult,
    StrategyType,
    UnifiedConfig,
)

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
    'SourceType',
    'StealthStrategy',
    'StrategyResult',
    'StrategyType',
    'UnifiedCache',
    'UnifiedConfig',
    'get_logger',
    'run_mcp_server',
]
