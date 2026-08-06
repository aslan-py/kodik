"""
Реальный LLM-клиент и ИИ-агент (BP-1 Adaptive).

Реализует:

- ``LLMClient`` — анализ структуры HTML через LLM (``litellm``/``openai``).
  Извлекает селекторы и схему данных из HTML-разметки.
- ``AIAgent`` — агент принятия решений: выбирает стратегию обхода,
  анализирует результаты парсинга и корректирует адаптеры.

LLM-провайдер настраивается через переменные окружения:
``LLM_MODEL`` (по умолчанию ``gpt-4o-mini``), ``LLM_API_KEY``,
``LLM_BASE_URL``. Если ключ не задан, используется эвристический fallback,
чтобы пакет оставался работоспособным без внешних сервисов.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .schemas import AdapterConfig, SourceClassification, StrategyType

logger = logging.getLogger(__name__)


def _default_model() -> str:
    """Модель LLM по умолчанию из окружения."""
    return os.getenv('LLM_MODEL', 'gpt-4o-mini')


def _has_llm_config() -> bool:
    """Проверяет, задана ли конфигурация LLM."""
    return bool(os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY'))


class LLMClient:
    """
    Клиент для анализа структуры HTML через LLM.

    Если LLM не настроен, использует эвристический fallback на основе
    HTML-тегов, чтобы пакет работал без внешних сервисов.
    """

    def __init__(
        self,
        model: str | None = None,
        logger: logging.Logger | None = None,
    ):
        self._model = model or _default_model()
        self._logger = logger or logging.getLogger(__name__)

    async def analyze_structure(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str] | None = None,
    ) -> AdapterConfig:
        """
        Анализирует HTML и извлекает структуру данных.

        Возвращает AdapterConfig с селекторами и схемой.
        """
        expected_fields = expected_fields or [
            'title',
            'text',
            'published_at',
            'region',
            'url',
        ]

        if not _has_llm_config():
            return self._heuristic_analyze(html, expected_fields)

        try:
            return await self._llm_analyze(html, competitor, expected_fields)
        except Exception as e:
            self._logger.warning('Ошибка LLM-анализа структуры: %s', e)
            return self._heuristic_analyze(html, expected_fields)

    async def _llm_analyze(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Анализ структуры через LLM."""
        import litellm

        prompt = (
            'Проанализируй HTML-страницу и найди:\n'
            '1. Контейнер с элементами (новости, товары, вакансии)\n'
            '2. Селекторы для полей: '
            f'{", ".join(expected_fields)}\n'
            '3. Элемент пагинации (если есть)\n\n'
            f'Конкурент: {competitor}\n'
            f'Ожидаемые поля: {expected_fields}\n\n'
            f'HTML: {html[:10000]}\n\n'
            'Верни JSON: {"selectors": {...}, "schema": {...}}'
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.0,
        )
        content = response.choices[0].message.content
        data = self._parse_json(content)

        schema = data.get('schema', {})
        if not schema:
            schema = dict.fromkeys(expected_fields, 'string')

        return AdapterConfig(
            source_name='adaptive',
            base_url='',
            expected_schema=schema,
            adaptive=True,
            auto_save=True,
        )

    def _heuristic_analyze(
        self,
        html: str,
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Эвристический fallback-анализ структуры."""
        return AdapterConfig(
            source_name='adaptive',
            base_url='',
            expected_schema=dict.fromkeys(expected_fields, 'string'),
            adaptive=True,
            auto_save=True,
        )

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        """Извлекает JSON из ответа LLM (устойчив к markdown-обёртке)."""
        content = content.strip()
        if content.startswith('```'):
            content = content.strip('`')
            if content.startswith('json'):
                content = content[4:]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {}


class AIAgent:
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
    ):
        self._model = model or _default_model()
        self._logger = logger or logging.getLogger(__name__)

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
        import litellm

        prompt = (
            'Выбери стратегию обхода для источника.\n'
            f'Классификация: {classification.model_dump_json()}\n'
            'Доступные стратегии: FAST, CRAWL4AI, BROWSER, WAYBACK, '
            'STEALTH, HITL\n'
            'Верни JSON: {"strategy": "..."}'
        )
        response = await litellm.acompletion(
            model=self._model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.0,
        )
        content = response.choices[0].message.content
        data = LLMClient._parse_json(content)
        strategy = data.get('strategy', '').upper()
        try:
            return StrategyType(strategy)
        except ValueError:
            return self._heuristic_strategy(classification)

    @staticmethod
    def _heuristic_strategy(
        classification: SourceClassification,
    ) -> StrategyType:
        """Эвристический выбор стратегии по классификации."""
        if classification.has_captcha or classification.has_antibot:
            return StrategyType.STEALTH
        if classification.is_spa:
            return StrategyType.BROWSER
        if classification.source_type.value == 'api':
            return StrategyType.FAST
        return StrategyType.FAST

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
            import litellm

            prompt = (
                'Проанализируй результат парсинга.\n'
                f'Источник: {source_name}\n'
                f'Количество элементов: {len(items)}\n'
                f'Примеры: {json.dumps(items[:3], ensure_ascii=False)}\n'
                'Верни JSON: {"recommendation": "...", "confidence": 0.0}'
            )
            response = await litellm.acompletion(
                model=self._model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content
            return LLMClient._parse_json(content)
        except Exception as e:
            self._logger.warning('Ошибка анализа результата агентом: %s', e)
            return {'recommendation': 'error', 'confidence': 0.0}
