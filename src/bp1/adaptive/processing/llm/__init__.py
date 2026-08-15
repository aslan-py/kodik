"""
Реальный LLM-клиент и ИИ-агент (BP-1 Adaptive).

Тонкий фасад поверх пакета ``_llm`` (см. ``processing/_llm``). Реализует:

- ``LLMClient`` (``client.py``) — анализ структуры HTML через LLM
  (``openai``). Извлекает **реальные CSS-селекторы** и схему данных из
  HTML-разметки.
- ``AIAgent`` (``agent.py``) — агент принятия решений: выбирает стратегию
  обхода, скорит релевантность, обогащает события и корректирует адаптеры.

Логика вынесена в модули ``_llm/``:
- ``constants`` — параметры и лимиты;
- ``prompts`` / ``prompt_builders`` — промпты и их сборка;
- ``schemas`` — типизированные ответы LLM;
- ``client`` — базовый клиент с ретраями/таймаутами;
- ``mappers`` — мапперы в доменные схемы;
- ``heuristics`` — эвристические fallback;
- ``chunking`` — параллельная обработка чанков;
- ``json_utils`` — устойчивый разбор JSON.
"""

from .agent import AIAgent
from .client import (
    LLMClient,
    _BaseLLMClient,
    _default_base_url,
    _default_model,
    _has_llm_config,
)

__all__ = [
    'AIAgent',
    'LLMClient',
    '_BaseLLMClient',
    '_default_base_url',
    '_default_model',
    '_has_llm_config',
]
