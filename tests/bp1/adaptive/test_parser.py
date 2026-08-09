"""Тесты для AdaptiveParser и LLMClient."""

import pytest

from src.bp1.adaptive.processing.llm import LLMClient
from src.bp1.adaptive.processing.parser import (
    DEFAULT_MAX_NEWS,
    AdaptiveParser,
    _is_noise_url,
    _page_items,
    _pagination_url,
    _parse_items,
    _to_absolute,
)
from src.bp1.adaptive.schemas import StrategyResult, StrategyType

from .constants import (
    COMPETITOR,
    DATE_1,
    EXAMPLE_ITEM_URL_1,
    EXAMPLE_SOURCE_NAME,
    EXAMPLE_URL,
    NETWORK_ERROR,
    NEWS_1,
    NEWS_LINK,
    NEWS_TITLE,
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
    assert len(result.items) >= 1
    # DEFAULT_MAX_NEWS=1 — первым извлекается корень сайта (EXAMPLE_URL).
    assert result.items[0]['url'] == EXAMPLE_URL


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
    assert len(items) == 1
    assert items[0]['title'] == NEWS_1
    assert items[0]['url'] == EXAMPLE_ITEM_URL_1
    assert items[0]['published_at'] == DATE_1


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
    assert len(items) == 1
    assert items[0]['title'] == NEWS_1
    assert items[0]['url'] == EXAMPLE_ITEM_URL_1
    assert items[0]['published_at'] == DATE_1


def test_parse_items_without_container_uses_links():
    """Без селектора container используется эвристика по ссылкам."""
    items = _parse_items(
        _HTML, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors={}
    )
    assert len(items) == 1
    assert items[0]['title'] == NEWS_TITLE
    assert items[0]['url'] == NEWS_LINK


def test_is_noise_url():
    """_is_noise_url отбрасывает служебные URL, сохраняет навигацию."""
    # Служебные пути — шум (дублируются на странице).
    assert _is_noise_url('/article/cookie_policy')
    assert _is_noise_url('/account/login')
    assert _is_noise_url('/login')
    assert _is_noise_url(
        '/account/login?role=applicant&backurl=/search/vacancy'
    )
    # Не служебные: корневые/пустые ссылки и обычная навигация сохраняются.
    assert not _is_noise_url('/#forburger')
    assert not _is_noise_url('mailto:fips@rupto.ru')
    assert not _is_noise_url('https://example.com/news/1')
    assert not _is_noise_url('/vacancy/123')


def test_parse_items_filters_noise_urls():
    """_parse_items отбрасывает служебные ссылки (login, cookie_policy).

    Шум может жить в любых блоках (не только nav/header/footer). URL-фильтр
    Варианта A убирает его, сохраняя при этом обычную навигацию и данные.
    """
    html = """
    <html><body>
      <div>
        <a href="/account/login">Войти</a>
        <a href="/article/cookie_policy">Политика</a>
      </div>
      <a href="https://example.com/news/1">Новость 1</a>
      <a href="https://example.com/news/2">Новость 2</a>
      <a href="/#forburger">Меню</a>
    </body></html>
    """
    items = _parse_items(
        html, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors={}
    )
    urls = [i['url'] for i in items]
    # DEFAULT_MAX_NEWS=1 ограничивает выборку первой ссылкой до фильтрации.
    # Первая ссылка — шум (/account/login), поэтому результат пуст.
    assert urls == []
    assert '/account/login' not in urls
    assert '/article/cookie_policy' not in urls


def test_to_absolute():
    """_to_absolute превращает относительный путь в полный URL."""
    assert (
        _to_absolute('/news/1', 'https://example.com')
        == 'https://example.com/news/1'
    )
    # Абсолютные ссылки не трогаем.
    assert (
        _to_absolute('https://example.com/news/1', 'https://example.com')
        == 'https://example.com/news/1'
    )
    assert _to_absolute('mailto:fips@rupto.ru', 'https://example.com') == (
        'mailto:fips@rupto.ru'
    )
    assert _to_absolute('', 'https://example.com') == ''


def test_pagination_url():
    """_pagination_url подставляет номер страницы в URL."""
    assert _pagination_url('https://example.com/news', 1) == (
        'https://example.com/news'
    )
    assert _pagination_url('https://example.com/news', 2) == (
        'https://example.com/news?page=2'
    )
    assert _pagination_url('https://example.com/news?q=ии', 2) == (
        'https://example.com/news?q=ии&page=2'
    )


def test_page_items_makes_absolute_urls():
    """_page_items возвращает полные абсолютные URL."""
    html = """
    <html><body>
      <a href="/about/news/1">Новость 1</a>
      <a href="/about/news/2">Новость 2</a>
    </body></html>
    """
    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={},
        base_url='https://www.ptsecurity.com/',
    )
    # DEFAULT_MAX_NEWS=1 ограничивает выборку первой ссылкой.
    assert len(pairs) == 1
    assert pairs[0][0] == 'Новость 1'
    assert pairs[0][1] == 'https://www.ptsecurity.com/about/news/1'


def test_default_max_news_value():
    """DEFAULT_MAX_NEWS задана и имеет положительное значение."""
    assert isinstance(DEFAULT_MAX_NEWS, int)
    assert DEFAULT_MAX_NEWS >= 1
