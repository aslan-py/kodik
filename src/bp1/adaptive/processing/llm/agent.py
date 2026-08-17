"""
AIAgent — ИИ-агент принятия решений для адаптивного сбора.

Использует LLM для:
- выбора оптимальной стратегии обхода по классификации источника;
- анализа результатов парсинга и корректировки адаптера.

Если LLM не настроен — везде используется эвристический fallback, чтобы
пакет оставался работоспособным без внешних сервисов.
"""

from __future__ import annotations

import logging
from typing import Any

from ...schemas import SourceClassification, StrategyType
from .._llm import constants, heuristics, prompt_builders
from .._llm.client import BaseLLMClient
from .._llm.json_utils import parse_json
from .._llm.schemas import ResultAnalysisResponse, StrategyResponse
from .client import _has_llm_config

logger = logging.getLogger(__name__)


class AIAgent(BaseLLMClient):
    """
    ИИ-агент принятия решений для адаптивного сбора.

    Использует LLM для:
    - выбора оптимальной стратегии обхода по классификации источника;
    - анализа результатов парсинга и корректировки адаптера.
    """

    def __init__(
        self,
        model: str | None = None,
        logger: logging.Logger | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__(
            model=model,
            logger=logger,
            base_url=base_url,
            api_key=api_key,
        )

    async def choose_strategy(
        self,
        classification: SourceClassification,
    ) -> StrategyType:
        """
        Выбирает стратегию обхода на основе классификации источника.

        Если LLM не настроен, использует эвристику по классификации.
        """
        if not _has_llm_config():
            return self._heuristic_strategy(classification)

        try:
            return await self._llm_choose_strategy(classification)
        except Exception as e:
            self._logger.warning('Ошибка выбора стратегии агентом: %s', e)
            return self._heuristic_strategy(classification)

    async def _llm_choose_strategy(
        self,
        classification: SourceClassification,
    ) -> StrategyType:
        """Выбор стратегии через LLM."""
        prompt = prompt_builders.build_strategy_prompt(
            classification.model_dump_json()
        )
        content = await self._complete(
            prompt,
            temperature=constants.TEMPERATURE_EXTRACTION,
        )
        data = parse_json(content or '') if content else {}
        response = StrategyResponse(**data)
        strategy = response.strategy.upper()
        try:
            return StrategyType(strategy)
        except ValueError:
            return self._heuristic_strategy(classification)

    @staticmethod
    def _heuristic_strategy(
        classification: SourceClassification,
    ) -> StrategyType:
        """Эвристический выбор стратегии по классификации."""
        return heuristics.heuristic_strategy(classification)

    async def analyze_result(
        self,
        html: str,
        items: list[dict[str, Any]],
        source_name: str,
    ) -> dict[str, Any]:
        """
        Анализирует результат парсинга и возвращает рекомендации.

        Возвращает словарь с рекомендациями по улучшению адаптера.
        """
        if not _has_llm_config():
            return {'recommendation': 'no_llm', 'confidence': 0.5}

        try:
            prompt = prompt_builders.build_result_analysis_prompt(
                source_name, items
            )
            content = await self._complete(
                prompt,
                temperature=constants.TEMPERATURE_GENERATIVE,
            )
            data = parse_json(content or '') if content else {}
            response = ResultAnalysisResponse(**data)
            return {
                'recommendation': response.recommendation,
                'confidence': response.confidence,
            }
        except Exception as e:
            self._logger.warning('Ошибка анализа результата агентом: %s', e)
            return {'recommendation': 'error', 'confidence': 0.0}
