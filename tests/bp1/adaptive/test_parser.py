"""Тесты для AdaptiveParser и LLMClient."""

import pytest

from src.bp1.adaptive.llm import LLMClient
from src.bp1.adaptive.parser import AdaptiveParser, _parse_items
from src.bp1.adaptive.schemas import StrategyResult, StrategyType

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
    config = await client.analyze_structure(_HTML, competitor='ООО АРХИТЕХ')
    assert 'title' in config.expected_schema
    assert 'url' in config.expected_schema
    assert config.adaptive is True


@pytest.mark.asyncio
async def test_parse_extracts_items():
    """AdaptiveParser извлекает элементы из HTML."""
    parser = AdaptiveParser()
    parser._orchestrator = _FakeOrchestrator()

    result = await parser.parse(
        url='https://example.com',
        source_name='example.com',
        competitor='ООО АРХИТЕХ',
        trigger='ИИ',
    )
    assert result.status == 'ok'
    assert len(result.items) >= 2
    assert result.items[0]['title'] == 'Новость про ИИ'
    assert result.items[0]['url'] == 'https://example.com/news/1'


@pytest.mark.asyncio
async def test_parse_failed_fetch_returns_error():
    """При неудачном fetch возвращается статус error."""
    parser = AdaptiveParser()

    class _FailingOrchestrator:
        async def fetch_with_degradation(self, url: str, **kwargs):
            return StrategyResult(
                strategy=StrategyType.FAST,
                success=False,
                error='network error',
            )

    parser._orchestrator = _FailingOrchestrator()
    result = await parser.parse(
        url='https://example.com',
        source_name='example.com',
    )
    assert result.status == 'error'
    assert 'network error' in (result.error or '')


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
        'container': 'div.item',
        'title': 'a.title',
        'url': 'a.title',
        'published_at': 'span.date',
    }
    items = _parse_items(
        html, 'example.com', 'ООО АРХИТЕХ', 'ИИ', selectors=selectors
    )
    assert len(items) == 2
    assert items[0]['title'] == 'Новость 1'
    assert items[0]['url'] == 'https://example.com/1'
    assert items[0]['published_at'] == '01.01.2026'
    assert items[1]['title'] == 'Новость 2'
