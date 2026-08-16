"""
AIAgent — ИИ-агент принятия решений для адаптивного сбора.

Использует LLM для:
- выбора оптимальной стратегии обхода по классификации источника;
- скоринга релевантности и обогащения событий структурированными полями;
- анализа результатов парсинга и корректировки адаптера.

Если LLM не настроен — везде используется эвристический fallback, чтобы
пакет оставался работоспособным без внешних сервисов.
"""

from __future__ import annotations

import logging
from typing import Any

from ...schemas import SourceClassification, StrategyType
from .._llm import constants, heuristics, mappers, prompt_builders
from .._llm.chunking import run_limited
from .._llm.client import BaseLLMClient
from .._llm.json_utils import parse_json
from .._llm.schemas import (
    EnrichmentResponse,
    RelevanceResponse,
    ResultAnalysisResponse,
    StrategyResponse,
)
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

    async def score_relevance(
        self,
        items: list[dict[str, Any]],
        competitor: str,
        trigger: str = '',
        inn: str | None = None,
    ) -> list[dict[str, Any]]:
        """Пакетный скоринг релевантности элементов относительно конкурента.

        Если LLM настроен — делит элементы на пачки по
        ``constants.RELEVANCE_BATCH_SIZE`` (Шаг 14 плана рефакторинга,
        REFACTORING_PLAN.md — N7) и обрабатывает их параллельно
        (``run_limited``). Раньше весь список уходил в LLM одним запросом:
        при росте числа элементов ответ рисковал упереться в
        ``RELEVANCE_MAX_TOKENS`` и обрезаться — ``parse_json`` тихо
        возвращал ``{}``, и на эвристику откатывался ВЕСЬ список, а не
        только "лишние" элементы. Батчирование ограничивает деградацию
        одной пачкой: сбой/усечение LLM-ответа для одной пачки не портит
        оценку остальных.

        Args:
            items: Собранные элементы ``(title, url, text)``.
            competitor: Название конкурента.
            trigger: Тема поиска (опционально).
            inn: ИНН конкурента (опционально).

        Returns:
            Список словарей ``{"index", "score", "relevant"}`` той же длины,
            что и ``items``, с ``index`` — сквозным по всему исходному
            списку (не по пачке).
        """
        if not items:
            return []

        if not _has_llm_config():
            return self._heuristic_relevance(items, competitor, trigger, inn)

        batch_size = constants.RELEVANCE_BATCH_SIZE
        batches: list[tuple[int, list[dict[str, Any]]]] = []
        offset = 0
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            batches.append((offset, batch))
            offset += len(batch)

        if len(batches) > 1:
            self._logger.info(
                'Скоринг релевантности: %d элементов -> %d пачек по %d',
                len(items),
                len(batches),
                batch_size,
            )

        batch_results = await run_limited(
            batches,
            lambda entry: self._score_relevance_batch(
                entry, competitor, trigger, inn
            ),
            constants.DEFAULT_PARALLEL_WORKERS,
            self._logger,
            'Ошибка обработки пачки релевантности: %s',
        )
        return [score for batch in batch_results for score in batch]

    async def _score_relevance_batch(
        self,
        entry: tuple[int, list[dict[str, Any]]],
        competitor: str,
        trigger: str,
        inn: str | None,
    ) -> list[dict[str, Any]]:
        """Скорит одну пачку элементов, возвращая сквозные (не локальные)
        индексы. Сбой LLM для этой пачки деградирует на эвристику только
        для неё — перехватывается здесь, наружу не пробрасывается."""
        batch_offset, batch = entry
        try:
            prompt = prompt_builders.build_relevance_prompt(
                batch, competitor, trigger
            )
            content = await self._complete(
                prompt,
                temperature=constants.TEMPERATURE_RELEVANCE,
                max_tokens=constants.RELEVANCE_MAX_TOKENS,
            )
            data = parse_json(content or '') if content else {}
            response = RelevanceResponse(**data)
            if not response.items:
                local_scores = self._heuristic_relevance(
                    batch, competitor, trigger, inn
                )
            else:
                local_scores = mappers.to_relevance_scores(batch, response)
        except Exception as e:
            self._logger.warning(
                'Ошибка LLM-скоринга релевантности пачки (offset=%d): %s',
                batch_offset,
                e,
            )
            local_scores = self._heuristic_relevance(
                batch, competitor, trigger, inn
            )
        return [
            {**score, 'index': score['index'] + batch_offset}
            for score in local_scores
        ]

    @staticmethod
    def _heuristic_relevance(
        items: list[dict[str, Any]],
        competitor: str,
        trigger: str = '',
        inn: str | None = None,
    ) -> list[dict[str, Any]]:
        """Эвристический скоринг релевантности (fallback без LLM)."""
        result: list[dict[str, Any]] = []
        for i, item in enumerate(items):
            text = (
                f'{item.get("title", "")} {item.get("text", "")} '
                f'{item.get("ex_text", "")}'
            )
            score = heuristics.heuristic_relevance_score(
                text, competitor, trigger, inn
            )
            result.append(
                {
                    'index': i,
                    'score': round(score, 3),
                    'relevant': score >= constants.DEFAULT_RELEVANCE_THRESHOLD,
                }
            )
        return result

    async def enrich_event(
        self,
        text: str,
        competitor: str,
        trigger: str = '',
    ) -> dict[str, Any]:
        """Обогащает текст события структурированными полями через LLM.

        Извлекает из полного текста ``published_at``, ``author``, ``keywords``,
        ``summary``, ``mentioned_company``, ``mentioned_inn``, ``sentiment``.
        При недоступности LLM или сбое возвращает пустой словарь.

        Args:
            text: Полный текст новости.
            competitor: Название конкурента.
            trigger: Тема поиска (опционально).

        Returns:
            Словарь с заполненными полями обогащения (пустые опущены).
        """
        if not _has_llm_config():
            return {}

        truncated = len(text) > constants.HTML_SNIPPET_SIZE
        if truncated:
            self._logger.info(
                'Промпт обогащения обрезан: %d -> %d символов. '
                'summary/sentiment/keywords посчитаны только по началу текста.',
                len(text),
                constants.HTML_SNIPPET_SIZE,
            )

        try:
            prompt = prompt_builders.build_enrichment_prompt(
                text, competitor, trigger
            )
            content = await self._complete(
                prompt,
                temperature=constants.TEMPERATURE_ENRICHMENT,
                max_tokens=constants.ENRICHMENT_MAX_TOKENS,
            )
            data = parse_json(content or '') if content else {}
            response = EnrichmentResponse(**data)
            result = mappers.to_enrichment(response)
            if truncated:
                # Пишем только когда True — как и остальные поля
                # to_enrichment, пустое/дефолтное значение не добавляется,
                # чтобы не менять смысл `if data:` у вызывающего кода
                # (пустой результат обогащения должен остаться пустым).
                result['enrichment_truncated'] = True
            return result
        except Exception as e:
            self._logger.warning('Ошибка LLM-обогащения события: %s', e)
            return {}

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
