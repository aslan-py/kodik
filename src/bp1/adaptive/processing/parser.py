"""
AdaptiveParser — интеллектуальный парсинг с анализом структуры HTML.

Поток:
1. Получить HTML через Orchestrator
2. Анализ структуры (извлечение селекторов)
3. Сохранение адаптера в кэш
4. Парсинг HTML в элементы
5. Валидация через Quality Gates
6. Конвертация в результат

Извлечение элементов по CSS-селекторам выполняется через ``BeautifulSoup``
(bs4), что обеспечивает корректную обработку вложенных контейнеров в
отличие от прежнего упрощённого ``HTMLParser``.
"""

from __future__ import annotations

import logging
import time
from html.parser import HTMLParser
from typing import Any

from bs4 import BeautifulSoup

from ..core.cache import UnifiedCache
from ..core.quality import DataQualityGate
from ..logger import new_trace_id
from ..schemas import (
    AdapterState,
    AdaptiveParseResult,
    StrategyType,
)
from ..strategies.orchestrator import AgenticOrchestrator
from .llm import AIAgent, LLMClient

logger = logging.getLogger(__name__)


class _LinkCollector(HTMLParser):
    """Собирает ссылки и заголовки из HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_text: list[str] = []
        self._in_a = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        if tag == 'a':
            self._in_a = True
            self._current_text = []
            href = dict(attrs).get('href')
            if href:
                self._pending_href = href

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self._in_a:
            self._in_a = False
            text = ' '.join(self._current_text).strip()
            href = getattr(self, '_pending_href', '')
            if text and href:
                self.links.append((text, href))


def _extract_by_selectors(
    html: str, selectors: dict[str, str]
) -> list[dict[str, str]]:
    """Извлекает элементы по CSS-селекторам через BeautifulSoup.

    Для каждого контейнера (``selectors['container']``) извлекает поля
    (title, text, url, published_at, region, media_name) по соответствующим
    селекторам. Корректно обрабатывает вложенные контейнеры.

    Args:
        html: Исходный HTML.
        selectors: Словарь ``{поле: css-селектор}``, где ``container`` —
            селектор контейнера элемента.

    Returns:
        Список извлечённых элементов (словарей с полями).
    """
    container_selector = (selectors.get('container') or '').strip()
    if not container_selector:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    containers = soup.select(container_selector)
    items: list[dict[str, str]] = []

    for container in containers:
        item: dict[str, str] = {}
        for field, selector in selectors.items():
            if field == 'container' or not selector:
                continue
            node = container.select_one(selector)
            if node is None:
                continue
            if field == 'url':
                href = node.get('href') or node.get('src') or ''
                item[field] = str(href).strip()
            else:
                text = node.get_text(' ', strip=True)
                if text:
                    item[field] = text
        if item:
            items.append(item)

    return items


class AdaptiveParser:
    """
    Интеллектуальный парсер с анализом структуры и адаптивным движком.

    Поток:
    1. Проверка кэша адаптеров
    2. Если адаптер есть → парсинг с сохранёнными селекторами
    3. Если адаптера нет → анализ структуры → генерация адаптера
    4. Сохранение адаптера в кэш
    5. Парсинг HTML в элементы
    6. Валидация качества
    7. Возврат результата
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        logger: logging.Logger | None = None,
        redis_client: Any = None,
    ):
        self._orchestrator = AgenticOrchestrator(
            headless=headless, timeout_ms=timeout
        )
        self._cache = UnifiedCache(redis_client=redis_client)
        self._quality_gate = DataQualityGate()
        self._llm_client = LLMClient(logger=logger)
        self._agent = AIAgent(logger=logger)
        self._logger = logger or logging.getLogger(__name__)

    def bind_redis(self, redis_client: Any) -> None:
        """Привязывает Redis-клиент к кэшу для хранения классификаций."""
        if self._cache.redis is None:
            self._cache.redis = redis_client

    async def parse(
        self,
        url: str,
        source_name: str,
        competitor: str = '',
        trigger: str = '',
        expected_schema: dict[str, Any] | None = None,
        **kwargs,
    ) -> AdaptiveParseResult:
        """
        Основной метод парсинга.

        1. Проверка кэша адаптеров
        2. Если адаптер есть → парсинг с сохранёнными селекторами
        3. Если адаптера нет → анализ структуры → генерация адаптера
        4. Сохранение адаптера в кэш
        5. Парсинг HTML в элементы
        6. Валидация качества
        7. Возврат результата
        """
        trace_id = new_trace_id()
        start = time.monotonic()

        # 1. Проверка кэша адаптеров.
        adapter = await self._cache.get_adapter(source_name)

        # 2. Получение HTML через оркестратор.
        #    Если классификация источника уже сохранена — начинаем с
        #    рекомендованной стратегии, чтобы не сканировать все подряд.
        start_with: StrategyType | None = None
        classification = await self._cache.get_classification(source_name)
        if classification is not None:
            try:
                start_with = StrategyType(classification.recommended_strategy)
            except ValueError:
                start_with = None

        strategy_result = await self._orchestrator.fetch_with_degradation(
            url,
            start_with=start_with,
            source_name=source_name,
        )
        if not strategy_result.success or not strategy_result.data:
            elapsed = int((time.monotonic() - start) * 1000)
            return AdaptiveParseResult(
                status='error',
                source_name=source_name,
                url=url,
                strategy_used=strategy_result.strategy,
                error=strategy_result.error or 'failed to fetch content',
                elapsed_ms=elapsed,
                trace_id=trace_id,
            )

        html = strategy_result.data

        # 3. Если адаптера нет — анализируем структуру и генерируем адаптер.
        if adapter is None:
            config = await self._llm_client.analyze_structure(
                html, competitor=competitor
            )
            adapter = AdapterState(
                source_name=source_name,
                # Реальные CSS-селекторы из LLM-анализа (не пустые строки).
                selectors=config.selectors,
                schema_config=config.expected_schema,
                confidence=config.confidence,
            )
            await self._cache.set_adapter(source_name, adapter)

        # 4. Парсинг HTML в элементы (с применением селекторов адаптера).
        items = _parse_items(
            html,
            source_name,
            competitor,
            trigger,
            selectors=adapter.selectors,
        )

        # 5. Валидация качества.
        reports = self._quality_gate.validate_all(items)
        quality_ok = self._quality_gate.is_all_passed(reports)

        elapsed = int((time.monotonic() - start) * 1000)
        return AdaptiveParseResult(
            status='ok' if quality_ok else 'low_quality',
            source_name=source_name,
            url=url,
            strategy_used=strategy_result.strategy,
            items=items,
            raw_text=html,
            adapter_version=adapter.version,
            elapsed_ms=elapsed,
            trace_id=trace_id,
        )


def _make_item(
    source_name: str,
    competitor: str,
    trigger: str,
    url: str,
    title: str,
    text: str | None = None,
    published_at: str | None = None,
    region: str | None = None,
    media_name: str | None = None,
) -> dict[str, Any]:
    """Формирует элемент данных из извлечённых полей."""
    return {
        'url': url,
        'title': title,
        'text': text,
        'published_at': published_at,
        'region': region,
        'media_name': media_name or source_name,
        'extra': {
            'competitor': competitor,
            'trigger': trigger,
        },
    }


def _parse_items(
    html: str,
    source_name: str,
    competitor: str,
    trigger: str,
    selectors: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Извлекает элементы из HTML.

    Если задан селектор ``container`` — извлекает элементы по селекторам
    адаптера (title, text, url, published_at, region) через BeautifulSoup.
    Иначе использует эвристический парсер ссылок: каждая ссылка с текстом
    становится кандидатом в элемент.
    """
    selectors = selectors or {}

    if selectors.get('container'):
        return [
            _make_item(
                source_name=source_name,
                competitor=competitor,
                trigger=trigger,
                url=raw.get('url', ''),
                title=raw.get('title', ''),
                text=raw.get('text'),
                published_at=raw.get('published_at'),
                region=raw.get('region'),
                media_name=raw.get('media_name'),
            )
            for raw in _extract_by_selectors(html, selectors)[:50]
        ]

    collector = _LinkCollector()
    collector.feed(html)

    return [
        _make_item(
            source_name=source_name,
            competitor=competitor,
            trigger=trigger,
            url=href,
            title=title,
        )
        for title, href in collector.links[:50]
    ]
