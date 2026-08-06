"""
AdaptiveParser — интеллектуальный парсинг с анализом структуры HTML.

Поток:
1. Получить HTML через Orchestrator
2. Анализ структуры (извлечение селекторов)
3. Сохранение адаптера в кэш
4. Парсинг HTML в элементы
5. Валидация через Quality Gates
6. Конвертация в результат
"""

from __future__ import annotations

import logging
import re
import time
from html.parser import HTMLParser
from typing import Any

from .cache import UnifiedCache
from .llm import AIAgent, LLMClient
from .logger import new_trace_id
from .orchestrator import AgenticOrchestrator
from .quality import DataQualityGate
from .schemas import (
    AdapterState,
    AdaptiveParseResult,
    StrategyType,
)

logger = logging.getLogger(__name__)


def _matches_selector(
    tag: str, attrs: list[tuple[str, str]], selector: str
) -> bool:
    """Проверяет, соответствует ли элемент CSS-селектору.

    Поддерживается простой синтаксис: ``tag``, ``.class``, ``#id``
    и их комбинации (например, ``div.item``, ``a.title``, ``div.item.active``).
    """
    selector = selector.strip()
    if not selector:
        return False

    attr_dict = dict(attrs)
    for part in selector.split():
        # Часть вида: tag, .class, #id, tag.class, tag#id, .class#id
        m = re.fullmatch(
            r'([a-zA-Z][\w-]*)?((?:\.[\w-]+)*)((?:#[\w-]+)*)', part
        )
        if not m:
            return False
        tag_part, classes_part, id_part = m.groups()

        if tag_part and tag != tag_part:
            return False
        for cls in classes_part.split('.'):
            if cls and cls not in attr_dict.get('class', '').split():
                return False
        if id_part and attr_dict.get('id') != id_part[1:]:
            return False
    return True


class _SelectorCollector(HTMLParser):
    """Извлекает элементы по CSS-селекторам.

    Собирает контейнеры по ``container`` и внутри каждого извлекает
    поля (title, text, url, published_at, region) по селекторам.
    """

    def __init__(self, selectors: dict[str, str]) -> None:
        super().__init__()
        self.selectors = selectors
        self.items: list[dict[str, str]] = []
        self._stack: list[tuple[str, dict[str, str]]] = []
        self._current: dict[str, str] | None = None
        self._field_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        container = self.selectors.get('container', '')
        if container and _matches_selector(tag, attrs, container):
            self._current = {}
            self._stack.append((tag, dict(attrs)))
            return

        if self._current is None:
            return

        # Один тег может соответствовать нескольким полям (например,
        # title и url с одинаковым селектором), поэтому обрабатываем все.
        for field, selector in self.selectors.items():
            if field == 'container':
                continue
            if _matches_selector(tag, attrs, selector):
                if field == 'url':
                    href = dict(attrs).get('href', '')
                    if href and self._current is not None:
                        self._current['url'] = href
                else:
                    self._field_stack.append(field)

        self._stack.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        if self._current is None or not self._field_stack:
            return
        field = self._field_stack[-1]
        text = data.strip()
        if not text:
            return
        if field == 'url':
            # URL берётся из атрибута href, а не из текста.
            return
        current = self._current.setdefault(field, '')
        self._current[field] = f'{current} {text}'.strip()

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        if self._field_stack and tag == self._stack[-1][0]:
            self._field_stack.pop()
        self._stack.pop()
        if self._current is not None and not self._stack:
            self.items.append(self._current)
            self._current = None


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
            url, start_with=start_with
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
    адаптера (title, text, url, published_at, region). Иначе использует
    эвристический парсер ссылок: каждая ссылка с текстом становится
    кандидатом в элемент.
    """
    selectors = selectors or {}
    items: list[dict[str, Any]] = []

    if selectors.get('container'):
        collector = _SelectorCollector(selectors)
        collector.feed(html)
        for raw in collector.items[:50]:
            items.append(
                {
                    'url': raw.get('url', ''),
                    'title': raw.get('title', ''),
                    'text': raw.get('text'),
                    'published_at': raw.get('published_at'),
                    'region': raw.get('region'),
                    'media_name': source_name,
                    'extra': {
                        'competitor': competitor,
                        'trigger': trigger,
                    },
                }
            )
        return items

    collector = _LinkCollector()
    collector.feed(html)

    for title, href in collector.links[:50]:
        items.append(
            {
                'url': href,
                'title': title,
                'text': None,
                'published_at': None,
                'region': None,
                'media_name': source_name,
                'extra': {
                    'competitor': competitor,
                    'trigger': trigger,
                },
            }
        )
    return items
