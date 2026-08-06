"""
Реальный LLM-клиент и ИИ-агент (BP-1 Adaptive).

Реализует:

- ``LLMClient`` — анализ структуры HTML через LLM (``openai``).
  Извлекает **реальные CSS-селекторы** и схему данных из HTML-разметки.
  Поддерживает умное чанкирование больших страниц через
  ``HtmlCleaner`` → ``StructuredChunker`` → параллельное извлечение →
  ``ResultMerger``.
- ``AIAgent`` — агент принятия решений: выбирает стратегию обхода,
  анализирует результаты парсинга и корректирует адаптеры.

LLM-провайдер настраивается через переменные окружения:
``LLM_MODEL`` (по умолчанию ``gpt-4o-mini``), ``LLM_API_KEY``,
``LLM_BASE_URL``. Если ключ не задан, используется эвристический fallback,
чтобы пакет оставался работоспособным без внешних сервисов.

Работа с LLM выполняется через официальный OpenAI SDK
(``openai.AsyncOpenAI``). Для OpenAI-совместимых API (например, DeepSeek)
достаточно задать ``LLM_BASE_URL``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from .chunker import Chunk, StructuredChunker
from .html_cleaner import HtmlCleaner
from .merger import ResultMerger
from .schemas import AdapterConfig, SourceClassification, StrategyType

logger = logging.getLogger(__name__)

# Корень проекта kodik/ — четыре уровня вверх от этого файла.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / '.env'

# Поля по умолчанию для анализа структуры.
_DEFAULT_FIELDS = [
    'title',
    'text',
    'published_at',
    'region',
    'url',
    'media_name',
]

# Параметры чанкирования по умолчанию.
_DEFAULT_MAX_CHUNK_SIZE = 8000
_DEFAULT_OVERLAP_SIZE = 500
_DEFAULT_MAX_CHUNKS = 10
_DEFAULT_PARALLEL_WORKERS = 5


def _default_model() -> str:
    """Модель LLM по умолчанию из окружения."""
    return os.getenv('LLM_MODEL', 'gpt-4o-mini')


def _default_base_url() -> str | None:
    """Базовый URL LLM-провайдера из окружения (если задан)."""
    return os.getenv('LLM_BASE_URL') or None


def _has_llm_config() -> bool:
    """Проверяет, задана ли конфигурация LLM."""
    return bool(os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY'))


def _load_env() -> None:
    """Загружает LLM-переменные из .env в os.environ (без python-dotenv).

    Использует ``setdefault``, чтобы не перезаписывать уже заданные
    переменные окружения (например, заданные в тестах через monkeypatch).
    """
    if not _ENV_PATH.exists():
        return
    for line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key.startswith('LLM_') or key == 'OPENAI_API_KEY':
            os.environ.setdefault(key, value)


_load_env()


class LLMClient:
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
        self._model = model or _default_model()
        self._base_url = base_url or _default_base_url()
        self._logger = logger or logging.getLogger(__name__)
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

        # OpenAI-клиент (AsyncOpenAI) создаётся лениво — только при первом
        # реальном обращении к LLM (когда задан ключ API). Это позволяет
        # создавать LLMClient без ключа (эвристический fallback).
        self._api_key = (
            api_key or os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY')
        )
        self._client = None

    def _get_client(self):
        """Лениво создаёт и возвращает AsyncOpenAI-клиент."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

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
            return self._heuristic_analyze(html, expected_fields)

        try:
            # Очистка HTML для оценки размера.
            cleaned = self._cleaner.clean(html)
            content = cleaned.get('content', '')
            if len(content) > self._max_chunk_size:
                return await self.analyze_structure_chunked(
                    html, competitor, expected_fields
                )
            return await self._llm_analyze(html, competitor, expected_fields)
        except Exception as e:
            self._logger.warning('Ошибка LLM-анализа структуры: %s', e)
            return self._heuristic_analyze(html, expected_fields)

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
            return self._heuristic_analyze(html, expected_fields)

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

        return self._to_adapter_config(merged, expected_fields)

    async def _extract_from_chunks(
        self,
        chunks: list[Chunk],
        competitor: str,
        expected_fields: list[str],
    ) -> list[dict[str, Any]]:
        """Параллельно извлекает структуру из чанков через LLM."""
        semaphore = asyncio.Semaphore(self._parallel_workers)

        async def _limited(chunk: Chunk) -> dict[str, Any]:
            async with semaphore:
                return await self._llm_analyze_chunk(
                    chunk, competitor, expected_fields
                )

        tasks = [_limited(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Отбрасываем ошибки, логируем их.
        valid: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                self._logger.warning('Ошибка анализа чанка: %s', result)
                continue
            if isinstance(result, dict):
                valid.append(result)
        return valid

    async def _llm_analyze(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Анализ структуры через LLM (один запрос)."""
        client = self._get_client()
        prompt = self._build_analysis_prompt(html, competitor, expected_fields)

        response = await client.chat.completions.create(
            model=self._model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.0,
        )
        content = response.choices[0].message.content
        data = self._parse_json(content)

        return self._to_adapter_config(data, expected_fields)

    async def _llm_analyze_chunk(
        self,
        chunk: Chunk,
        competitor: str,
        expected_fields: list[str],
    ) -> dict[str, Any]:
        """Анализ структуры одного чанка через LLM."""
        client = self._get_client()
        prompt = self._build_chunk_prompt(chunk, competitor, expected_fields)

        response = await client.chat.completions.create(
            model=self._model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.0,
        )
        content = response.choices[0].message.content
        data = self._parse_json(content)

        # Нормализуем результат чанка: selectors + schema + confidence.
        return {
            'selectors': data.get('selectors', {}),
            'schema': data.get('schema', {}),
            'confidence': data.get('confidence', 0.0),
            'metadata': data.get('metadata', {}),
        }

    def _build_analysis_prompt(
        self,
        html: str,
        competitor: str,
        expected_fields: list[str],
    ) -> str:
        """Строит промпт для анализа структуры страницы."""
        return (
            'Ты — эксперт по анализу HTML-страниц и извлечению '
            'структурированных данных.\n\n'
            '## Задача:\n'
            'Проанализируй HTML-код страницы и определи CSS-селекторы '
            'для извлечения данных.\n\n'
            '## Входные данные:\n'
            f'- Конкурент: {competitor}\n'
            f'- Ожидаемые поля: {expected_fields}\n'
            f'- HTML: {html[: self._max_chunk_size]}\n\n'
            '## Требования:\n'
            '1. Найди контейнер, который содержит список элементов '
            '(новости, вакансии, товары)\n'
            '2. Для каждого поля определи CSS-селектор\n'
            '3. Определи схему данных (типы полей)\n'
            '4. Найди пагинацию (если есть)\n\n'
            '## Ответь ТОЛЬКО в формате JSON:\n'
            '{\n'
            '    "selectors": {\n'
            '        "container": "article, .news-item, .vacancy-card, '
            '.product-item, .post",\n'
            '        "title": "h1, h2, h3, .title, .post-title, '
            '.vacancy-name, .item-title",\n'
            '        "text": ".content, .description, .post-content, '
            '.vacancy-description, .item-description",\n'
            '        "published_at": ".date, time, .published, '
            '.publish-date, .item-date",\n'
            '        "region": ".region, .location, .city, .address",\n'
            '        "media_name": ".source, .media, .publisher, '
            '.site-name",\n'
            '        "url": "a[href]"\n'
            '    },\n'
            '    "schema": {\n'
            '        "title": "string",\n'
            '        "text": "string",\n'
            '        "published_at": "string",\n'
            '        "region": "string",\n'
            '        "url": "string",\n'
            '        "media_name": "string"\n'
            '    },\n'
            '    "confidence": 0.85,\n'
            '    "metadata": {\n'
            '        "has_pagination": true,\n'
            '        "pagination_selector": "a.next, .pagination .next, '
            '.pager-next",\n'
            '        "items_per_page": 20\n'
            '    }\n'
            '}\n\n'
            '## Правила:\n'
            '1. Селекторы должны быть максимально специфичными, но '
            'устойчивыми к изменениям\n'
            '2. Используй data-атрибуты если они есть (они более стабильны)\n'
            '3. Для контейнера используй тег + класс (например, '
            'article.news-item)\n'
            '4. Для полей используй классы с описательными названиями\n'
            '5. Если поле не найдено, оставь пустую строку\n'
            '6. Confidence — уверенность в извлечении (0.0-1.0)\n'
            '7. Если есть пагинация — укажи селектор для кнопки "далее"'
        )

    def _build_chunk_prompt(
        self,
        chunk: Chunk,
        competitor: str,
        expected_fields: list[str],
    ) -> str:
        """Строит промпт для анализа одного чанка."""
        return (
            'Ты — эксперт по анализу HTML-страниц и извлечению '
            'структурированных данных.\n\n'
            '## Задача:\n'
            'Проанализируй фрагмент HTML-страницы и определи CSS-селекторы '
            'для извлечения данных.\n\n'
            '## Входные данные:\n'
            f'- Конкурент: {competitor}\n'
            f'- Ожидаемые поля: {expected_fields}\n'
            f'- Фрагмент HTML (часть {chunk.index}):\n'
            f'{chunk.content}\n\n'
            '## Требования:\n'
            '1. Найди контейнер, который содержит список элементов\n'
            '2. Для каждого поля определи CSS-селектор\n'
            '3. Определи схему данных (типы полей)\n\n'
            '## Ответь ТОЛЬКО в формате JSON:\n'
            '{\n'
            '    "selectors": {\n'
            '        "container": "",\n'
            '        "title": "",\n'
            '        "text": "",\n'
            '        "published_at": "",\n'
            '        "region": "",\n'
            '        "media_name": "",\n'
            '        "url": "a[href]"\n'
            '    },\n'
            '    "schema": {},\n'
            '    "confidence": 0.0,\n'
            '    "metadata": {}\n'
            '}\n\n'
            '## Правила:\n'
            '1. Извлекай ТОЛЬКО из этого фрагмента\n'
            '2. Если поле не найдено, оставь пустую строку\n'
            '3. Confidence — уверенность в извлечении (0.0-1.0)'
        )

    def _to_adapter_config(
        self,
        data: dict[str, Any],
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Формирует AdapterConfig из данных анализа."""
        selectors = data.get('selectors', {})
        schema = data.get('schema', {})

        if not isinstance(selectors, dict):
            selectors = {}
        if not isinstance(schema, dict):
            schema = {}

        # Нормализация селекторов: только строковые значения.
        selectors = {
            k: (v if isinstance(v, str) else '') for k, v in selectors.items()
        }

        # Если схема пустая — заполняем из ожидаемых полей.
        if not schema:
            schema = dict.fromkeys(expected_fields, 'string')

        # Confidence из данных анализа (0.0-1.0).
        confidence = data.get('confidence', 0.0)
        if not isinstance(confidence, int | float):
            confidence = 0.0
        confidence = max(0.0, min(1.0, float(confidence)))

        return AdapterConfig(
            source_name='adaptive',
            base_url='',
            expected_schema=schema,
            selectors=selectors,
            confidence=confidence,
            adaptive=True,
            auto_save=True,
        )

    def _heuristic_analyze(
        self,
        html: str,
        expected_fields: list[str],
    ) -> AdapterConfig:
        """Эвристический fallback-анализ структуры.

        Возвращает схему из ожидаемых полей и пустые селекторы (кроме
        ``url`` — ``a[href]``), чтобы парсер мог использовать эвристику
        по ссылкам.
        """
        return AdapterConfig(
            source_name='adaptive',
            base_url='',
            expected_schema=dict.fromkeys(expected_fields, 'string'),
            selectors={'url': 'a[href]'},
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
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self._model = model or _default_model()
        self._base_url = base_url or _default_base_url()
        self._logger = logger or logging.getLogger(__name__)

        # OpenAI-клиент (AsyncOpenAI) создаётся лениво — только при первом
        # реальном обращении к LLM (когда задан ключ API).
        self._api_key = (
            api_key or os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY')
        )
        self._client = None

    def _get_client(self):
        """Лениво создаёт и возвращает AsyncOpenAI-клиент."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

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
        client = self._get_client()
        prompt = (
            'Выбери стратегию обхода для источника.\n'
            f'Классификация: {classification.model_dump_json()}\n'
            'Доступные стратегии: FAST, CRAWL4AI, BROWSER, WAYBACK, '
            'STEALTH, HITL\n'
            'Верни JSON: {"strategy": "..."}'
        )
        response = await client.chat.completions.create(
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
            client = self._get_client()
            prompt = (
                'Проанализируй результат парсинга.\n'
                f'Источник: {source_name}\n'
                f'Количество элементов: {len(items)}\n'
                f'Примеры: {json.dumps(items[:3], ensure_ascii=False)}\n'
                'Верни JSON: {"recommendation": "...", "confidence": 0.0}'
            )
            response = await client.chat.completions.create(
                model=self._model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.0,
            )
            content = response.choices[0].message.content
            return LLMClient._parse_json(content)
        except Exception as e:
            self._logger.warning('Ошибка анализа результата агентом: %s', e)
            return {'recommendation': 'error', 'confidence': 0.0}
