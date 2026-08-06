"""Тесты для AdaptiveParser и LLMClient."""

import pytest

from src.bp1.adaptive.processing.llm import LLMClient
from src.bp1.adaptive.processing.parser import AdaptiveParser, _parse_items
from src.bp1.adaptive.schemas import StrategyResult, StrategyType

from .constants import (
    COMPETITOR,
    DATE_1,
    DATE_2,
    EXAMPLE_ITEM_URL_1,
    EXAMPLE_ITEM_URL_2,
    EXAMPLE_SOURCE_NAME,
    EXAMPLE_URL,
    NETWORK_ERROR,
    NEWS_1,
    NEWS_2,
    NEWS_LINK,
    NEWS_LINK_2,
    NEWS_TITLE,
    NEWS_TITLE_2,
    PARSER_STATUS_ERROR,
    PARSER_STATUS_OK,
    SELECTOR_CONTAINER,
    SELECTOR_DATE,
    SELECTOR_TITLE,
    SELECTOR_URL,
    TRIGGER,
)

_HTML = """
<html>
<body>
  <a href="https://example.com/news/1">Новость про ИИ</a>
  <a href="https://example.com/news/2">Новость про нейросети</a>
</body>
</html>
"""


class _FakeOrchestrator:
    """Оркестратор-заглушка, возвращающий фиксированный HTML."""

    async def fetch_with_degradation(self, url: str, **kwargs):
        return StrategyResult(
            strategy=StrategyType.FAST,
            success=True,
            data=_HTML,
            content_length=len(_HTML),
        )


@pytest.mark.asyncio
async def test_llm_analyze_structure():
    """LLMClient возвращает AdapterConfig со схемой."""
    client = LLMClient()
    config = await client.analyze_structure(_HTML, competitor=COMPETITOR)
    assert 'title' in config.expected_schema
    assert 'url' in config.expected_schema
    assert config.adaptive is True


@pytest.mark.asyncio
async def test_parse_extracts_items(monkeypatch):
    """AdaptiveParser извлекает элементы из HTML."""
    # Очищаем ключи LLM, чтобы использовалась эвристика (сбор ссылок),
    # а не реальный LLM-путь (не зависеть от .env).
    monkeypatch.delenv('LLM_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    parser = AdaptiveParser()
    parser._orchestrator = _FakeOrchestrator()

    result = await parser.parse(
        url=EXAMPLE_URL,
        source_name=EXAMPLE_SOURCE_NAME,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    assert result.status == PARSER_STATUS_OK
    assert len(result.items) >= 2
    assert result.items[0]['title'] == NEWS_TITLE
    assert result.items[0]['url'] == NEWS_LINK


@pytest.mark.asyncio
async def test_parse_failed_fetch_returns_error():
    """При неудачном fetch возвращается статус error."""
    parser = AdaptiveParser()

    class _FailingOrchestrator:
        async def fetch_with_degradation(self, url: str, **kwargs):
            return StrategyResult(
                strategy=StrategyType.FAST,
                success=False,
                error=NETWORK_ERROR,
            )

    parser._orchestrator = _FailingOrchestrator()
    result = await parser.parse(
        url=EXAMPLE_URL,
        source_name=EXAMPLE_SOURCE_NAME,
    )
    assert result.status == PARSER_STATUS_ERROR
    assert NETWORK_ERROR in (result.error or '')


def test_parse_items_with_selectors():
    """_parse_items извлекает поля по селекторам адаптера."""
    html = """
    <html><body>
      <div class="item">
        <a class="title" href="https://example.com/1">Новость 1</a>
        <span class="date">01.01.2026</span>
      </div>
      <div class="item">
        <a class="title" href="https://example.com/2">Новость 2</a>
        <span class="date">02.01.2026</span>
      </div>
    </body></html>
    """
    selectors = {
        'container': SELECTOR_CONTAINER,
        'title': SELECTOR_TITLE,
        'url': SELECTOR_URL,
        'published_at': SELECTOR_DATE,
    }
    items = _parse_items(
        html, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors=selectors
    )
    assert len(items) == 2
    assert items[0]['title'] == NEWS_1
    assert items[0]['url'] == EXAMPLE_ITEM_URL_1
    assert items[0]['published_at'] == DATE_1
    assert items[1]['title'] == NEWS_2
    assert items[1]['url'] == EXAMPLE_ITEM_URL_2


def test_parse_items_nested_containers():
    """_parse_items корректно обрабатывает вложенные контейнеры (bs4)."""
    html = """
    <html><body>
      <div class="feed">
        <div class="item">
          <a class="title" href="https://example.com/1">Новость 1</a>
          <span class="date">01.01.2026</span>
        </div>
        <div class="item">
          <a class="title" href="https://example.com/2">Новость 2</a>
          <span class="date">02.01.2026</span>
        </div>
      </div>
    </body></html>
    """
    selectors = {
        'container': SELECTOR_CONTAINER,
        'title': SELECTOR_TITLE,
        'url': SELECTOR_URL,
        'published_at': SELECTOR_DATE,
    }
    items = _parse_items(
        html, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors=selectors
    )
    assert len(items) == 2
    assert items[0]['title'] == NEWS_1
    assert items[0]['url'] == EXAMPLE_ITEM_URL_1
    assert items[0]['published_at'] == DATE_1
    assert items[1]['title'] == NEWS_2
    assert items[1]['published_at'] == DATE_2
    assert items[1]['url'] == EXAMPLE_ITEM_URL_2


def test_parse_items_without_container_uses_links():
    """Без селектора container используется эвристика по ссылкам."""
    items = _parse_items(
        _HTML, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors={}
    )
    assert len(items) == 2
    assert items[0]['title'] == NEWS_TITLE
    assert items[0]['url'] == NEWS_LINK
    assert items[1]['title'] == NEWS_TITLE_2
    assert items[1]['url'] == NEWS_LINK_2
