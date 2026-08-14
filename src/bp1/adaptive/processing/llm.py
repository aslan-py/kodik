"""
Реальный LLM-клиент и ИИ-агент (BP-1 Adaptive).

Тонкий фасад поверх пакета ``llm`` (см. ``processing/llm``). Реализует:

- ``LLMClient`` — анализ структуры HTML через LLM (``openai``).
  Извлекает **реальные CSS-селекторы** и схему данных из HTML-разметки.
  Поддерживает умное чанкирование больших страниц через
  ``HtmlCleaner`` → ``StructuredChunker`` → параллельное извлечение →
  ``ResultMerger``.
- ``AIAgent`` — агент принятия решений: выбирает стратегию обхода,
  анализирует результаты парсинга и корректирует адаптеры.

LLM-провайдер настраивается через ``core.config.settings``: ``llm_model``
(по умолчанию ``gpt-4o-mini``), ``llm_api_key``, ``llm_base_url``. Если ключ
не задан, используется эвристический fallback, чтобы пакет оставался
работоспособным без внешних сервисов.

Логика вынесена в модули:
- ``constants`` — параметры и лимиты;
- ``prompts`` / ``prompt_builders`` — промпты и их сборка;
- ``schemas`` — типизированные ответы LLM;
- ``client`` — базовый клиент с ретраями/таймаутами;
- ``mappers`` — мапперы в доменные схемы;
- ``heuristics`` — эвристические fallback;
- ``chunking`` — параллельная обработка чанков;
- ``json_utils`` — устойчивый разбор JSON.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from ..schemas import (
    AdapterConfig,
    ExtendedSiteClassification,
    SourceClassification,
    StrategyType,
)
from ._llm import constants, heuristics, mappers, prompt_builders
from ._llm.chunking import run_limited
from ._llm.client import BaseLLMClient, default_model, has_llm_config
from ._llm.json_utils import parse_json
from ._llm.schemas import (
    ClassificationResponse,
    EnrichmentResponse,
    RelevanceResponse,
    ResultAnalysisResponse,
    SelectorExtractionResponse,
    StrategyResponse,
)
from .chunker import Chunk, StructuredChunker
from .html_cleaner import HtmlCleaner
from .merger import ResultMerger

logger = logging.getLogger(__name__)

# Поля по умолчанию для анализа структуры.
_DEFAULT_FIELDS = constants.DEFAULT_FIELDS

# Параметры чанкирования по умолчанию.
_DEFAULT_MAX_CHUNK_SIZE = constants.DEFAULT_MAX_CHUNK_SIZE
_DEFAULT_OVERLAP_SIZE = constants.DEFAULT_OVERLAP_SIZE
_DEFAULT_MAX_CHUNKS = constants.DEFAULT_MAX_CHUNKS
_DEFAULT_PARALLEL_WORKERS = constants.DEFAULT_PARALLEL_WORKERS


# ---------------------------------------------------------------------------
# Совместимые алиасы (для внешних потребителей).
# ---------------------------------------------------------------------------


def _default_model() -> str:
    """Модель LLM по умолчанию из настроек."""
    return default_model()


def _default_base_url() -> str | None:
    """Базовый URL LLM-провайдера из настроек (если задан)."""
    from ._llm.client import default_base_url as _dbu

    return _dbu()


def _has_llm_config() -> bool:
    """Проверяет, задана ли конфигурация LLM."""
    return has_llm_config()


# Промпт, сохранённый для обратной совместимости (при необходимости).
from ._llm.prompts import SITE_CLASSIFICATION_PROMPT_V2  # noqa: E402,F401


class _BaseLLMClient(BaseLLMClient):
    """Обратно совместимый алиас на базовый клиент."""


class LLMClient(BaseLLMClient):
    """
    Клиент для анализа структуры HTML через LLM.

    Возвращает ``AdapterConfig`` с заполненными ``selectors`` (реальные
    CSS-селекторы) и ``expected_schema`` (типы полей). Если LLM не настроен,
    использует эвристический fallback на основе HTML-тегов, чтобы пакет
    работал без внешних сервисов.
    """

    def __init__(
        self,
        model: str | None = None,
        logger: logging.Logger | None = None,
        max_chunk_size: int = _DEFAULT_MAX_CHUNK_SIZE,
        overlap_size: int = _DEFAULT_OVERLAP_SIZE,
        max_chunks: int = _DEFAULT_MAX_CHUNKS,
        parallel_workers: int = _DEFAULT_PARALLEL_WORKERS,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__(
            model=model,
            logger=logger,
            base_url=base_url,
            api_key=api_key,
        )
        self._max_chunk_size = max_chunk_size
        self._overlap_size = overlap_size
        self._max_chunks = max_chunks
        self._parallel_workers = parallel_workers

        self._cleaner = HtmlCleaner()
        self._chunker = StructuredChunker(
            max_chunk_size=max_chunk_size,
            overlap_size=overlap_size,
        )
        self._merger = ResultMerger()

    # ------------------------------------------------------------------
    # Извлечение текста статьи.
    # ------------------------------------------------------------------

    async def extract_article_text(self, content: str) -> str | None:
        """Извлекает основной текст статьи из очищенного HTML через LLM.

        Используется глубоким фетчем (каскад CSS → LLM → сниппет) для
        получения полного текста новости со страницы статьи. Если LLM не
        настроен или запрос не удался — возвращает ``None`` (передаёт
        управление следующему способу извлечения).

        Длинные статьи (больше ``_max_chunk_size``) обрабатываются по
        частям через ``StructuredChunker``: каждая часть извлекается
        отдельным запросом, результаты склеиваются.

        Args:
            content: Очищенный HTML статьи (см. ``HtmlCleaner.clean``).

        Returns:
            Полный текст статьи или ``None`` при недоступности LLM.
        """
        if not _has_llm_config():
            return None
        try:
            if len(content) <= self._max_chunk_size:
                text = await self._llm_extract_single(content)
            else:
                text = await self._llm_extract_chunked(content)
            return (text or '').strip() or None
        except Exception as e:
            self._logger.warning('Ошибка LLM-извлечения статьи: %s', e)
            return None

    async def _llm_extract_single(self, content: str) -> str | None:
        """Один LLM-запрос: извлечь основной текст из фрагмента HTML."""
        prompt = prompt_builders.build_article_text_prompt(content)
        return await self._complete(
            prompt,
            temperature=constants.TEMPERATURE_EXTRACTION,
        )

    async def _llm_extract_chunked(self, content: str) -> str | None:
        """Чанкированное извлечение текста для длинных статей.

        Разбивает очищенный HTML на части ``StructuredChunker`` (до
        ``_max_chunks`` штук), извлекает текст из каждой части параллельно
        (семафор ``_parallel_workers``) и склеивает результаты.
        """
        cleaned: dict[str, Any] = {'content': content, 'blocks': []}
        chunks = self._chunker.chunk(cleaned)[: self._max_chunks]
        if not chunks:
            return None

        async def _extract(chunk: Chunk) -> str | None:
            return await self._llm_extract_single(chunk.content)

        results = await run_limited(
            chunks,
            _extract,
            self._parallel_workers,
            self._logger,
            'Ошибка LLM-извлечения чанка: %s',
        )
        parts: list[str] = []
        for result in results:
            if isinstance(result, str) and result.strip():
                parts.append(result)
        return '\n\n'.join(parts) or None

    # ------------------------------------------------------------------
    # Анализ структуры.
    # ------------------------------------------------------------------

    async def analyze_structure(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str] | None = None,
    ) -> AdapterConfig:
        """
        Анализирует HTML и извлекает структуру данных.

        Возвращает ``AdapterConfig`` с реальными CSS-селекторами
        (``selectors``) и схемой (``expected_schema``).

        Для больших страниц (> ``max_chunk_size``) автоматически использует
        чанкирование через ``analyze_structure_chunked``.
        """
        expected_fields = expected_fields or list(_DEFAULT_FIELDS)

        if not _has_llm_config():
            return heuristics.heuristic_analyze(html, expected_fields)

        try:
            # Очистка HTML: сжимаем объём и извлекаем основной контент.
            cleaned = self._cleaner.clean(html)
            content = cleaned.get('content', '')
            if not content:
                return heuristics.heuristic_analyze(html, expected_fields)

            if len(content) > self._max_chunk_size:
                return await self.analyze_structure_chunked(
                    html, competitor, expected_fields
                )
            return await self._llm_analyze(content, competitor, expected_fields)
        except Exception as e:
            self._logger.warning('Ошибка LLM-анализа структуры: %s', e)
            return heuristics.heuristic_analyze(html, expected_fields)

    async def analyze_structure_chunked(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str] | None = None,
        max_chunk_size: int | None = None,
    ) -> AdapterConfig:
        """
        Анализирует структуру с чанкированием для больших HTML.

        1. Очистка HTML (``HtmlCleaner``).
        2. Разбиение на логические чанки с перекрытием (``StructuredChunker``).
        3. Параллельный анализ каждого чанка через LLM.
        4. Объединение результатов (``ResultMerger``).
        """
        expected_fields = expected_fields or list(_DEFAULT_FIELDS)
        chunk_size = max_chunk_size or self._max_chunk_size

        # 1. Очистка и сжатие.
        cleaned = self._cleaner.clean(html)

        # 2. Умное чанкирование.
        chunker = self._chunker
        if chunk_size != self._max_chunk_size:
            chunker = StructuredChunker(
                max_chunk_size=chunk_size,
                overlap_size=self._overlap_size,
            )
        chunks = chunker.chunk(cleaned)
        if not chunks:
            return heuristics.heuristic_analyze(html, expected_fields)

        # Ограничение числа чанков.
        chunks = chunks[: self._max_chunks]

        # 3. Параллельное извлечение из чанков.
        results = await self._extract_from_chunks(
            chunks, competitor, expected_fields
        )

        # 4. Объединение результатов.
        merged = self._merger.merge(
            results=results,
            chunk_metadata=[c.metadata for c in chunks],
        )

        return mappers.to_adapter_config(
            SelectorExtractionResponse(**merged), expected_fields
        )

    async def _extract_from_chunks(
        self,
        chunks: list[Chunk],
        competitor: str,
        expected_fields: list[str],
    ) -> list[dict[str, Any]]:
        """Параллельно извлекает структуру из чанков через LLM."""
        results = await run_limited(
            chunks,
            lambda chunk: self._llm_analyze_chunk(
                chunk, competitor, expected_fields
            ),
            self._parallel_workers,
            self._logger,
            'Ошибка анализа чанка: %s',
        )
        return [r for r in results if isinstance(r, dict)]

    async def _llm_analyze(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Анализ структуры через LLM (один запрос)."""
        prompt = prompt_builders.build_analysis_prompt(
            html, competitor, expected_fields
        )
        content = await self._complete(
            prompt,
            temperature=constants.TEMPERATURE_EXTRACTION,
            max_tokens=constants.ANALYZE_MAX_TOKENS,
        )
        data = parse_json(content or '') if content else {}
        response = SelectorExtractionResponse(**data)
        return mappers.to_adapter_config(response, expected_fields)

    async def _llm_analyze_chunk(
        self,
        chunk: Chunk,
        competitor: str,
        expected_fields: list[str],
    ) -> dict[str, Any]:
        """Анализ структуры одного чанка через LLM."""
        prompt = prompt_builders.build_chunk_prompt(
            chunk, competitor, expected_fields
        )
        content = await self._complete(
            prompt,
            temperature=constants.TEMPERATURE_EXTRACTION,
            max_tokens=constants.ANALYZE_MAX_TOKENS,
        )
        data = parse_json(content or '') if content else {}
        response = SelectorExtractionResponse(**data)

        # Нормализуем результат чанка: selectors + schema + confidence.
        return {
            'selectors': response.selectors,
            'schema': response.schema,
            'confidence': response.confidence,
            'metadata': response.metadata,
        }

    # ------------------------------------------------------------------
    # Классификация сайта.
    # ------------------------------------------------------------------

    async def classify_with_llm(
        self,
        html: str,
        url: str,
        headers: dict[str, Any] | None = None,
    ) -> ExtendedSiteClassification:
        """Расширенная классификация сайта через LLM.

        Определяет ``SiteType``, подтип страницы, бизнес- и технические
        характеристики. Если LLM не настроен или произошла ошибка —
        использует эвристический fallback.
        """
        if not _has_llm_config():
            return heuristics.heuristic_classify(html, url)

        try:
            # Очистка HTML перед передачей в LLM.
            cleaned = self._cleaner.clean(html)
            content = cleaned.get('content', '') or html

            # Извлечение заголовка и описания.
            soup = BeautifulSoup(content, 'html.parser')
            title_node = soup.find('title')
            title = title_node.get_text(strip=True) if title_node else ''
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ''

            prompt = prompt_builders.build_classification_prompt(
                url, title, description, content
            )
            raw = await self._complete(
                prompt,
                temperature=constants.TEMPERATURE_EXTRACTION,
                max_tokens=constants.CLASSIFY_MAX_TOKENS,
            )
            data = parse_json(raw or '') if raw else {}
            response = ClassificationResponse(**data)
            return mappers.to_extended_classification(
                response, url, headers or {}
            )
        except Exception as e:
            self._logger.warning('Ошибка LLM-классификации: %s', e)
            return heuristics.heuristic_classify(html, url)

    # ------------------------------------------------------------------
    # Мапперы / хевистики (обратная совместимость).
    # ------------------------------------------------------------------

    def _build_classification_prompt(
        self,
        url: str,
        title: str,
        description: str,
        html: str,
    ) -> str:
        """Строит промпт детальной классификации сайта."""
        return prompt_builders.build_classification_prompt(
            url, title, description, html
        )

    def _build_analysis_prompt(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str],
    ) -> str:
        """Строит промпт для анализа структуры страницы."""
        return prompt_builders.build_analysis_prompt(
            html, competitor, expected_fields
        )

    def _build_chunk_prompt(
        self,
        chunk: Chunk,
        competitor: str,
        expected_fields: list[str],
    ) -> str:
        """Строит промпт для анализа одного чанка."""
        return prompt_builders.build_chunk_prompt(
            chunk, competitor, expected_fields
        )

    def _to_adapter_config(
        self,
        data: dict[str, Any],
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Формирует AdapterConfig из данных анализа."""
        return mappers.to_adapter_config(
            SelectorExtractionResponse(**data), expected_fields
        )

    def _to_extended_classification(
        self,
        data: dict[str, Any],
        html: str,
        url: str,
        headers: dict[str, Any],
    ) -> ExtendedSiteClassification:
        """Формирует ``ExtendedSiteClassification`` из JSON-ответа LLM."""
        return mappers.to_extended_classification(
            ClassificationResponse(**data), url, headers
        )

    def _heuristic_classify(
        self,
        html: str,
        url: str,
    ) -> ExtendedSiteClassification:
        """Эвристическая классификация (fallback без LLM)."""
        return heuristics.heuristic_classify(html, url)

    def _heuristic_analyze(
        self,
        html: str,
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Эвристический fallback-анализ структуры."""
        return heuristics.heuristic_analyze(html, expected_fields)

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        """Извлекает JSON из ответа LLM (устойчив к markdown-обёртке)."""
        return parse_json(content)


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
            return mappers.to_enrichment(response)
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
