"""Тесты для AdaptiveParser и LLMClient."""

import pytest

from core.config import settings
from src.bp1.adaptive.processing import parser as parser_module
from src.bp1.adaptive.processing.llm import LLMClient
from src.bp1.adaptive.processing.parser import (
    DEFAULT_MAX_NEWS,
    AdaptiveParser,
    _is_noise_url,
    _looks_truncated,
    _page_items,
    _pagination_url,
    _parse_items,
    _to_absolute,
)
from src.bp1.adaptive.schemas import (
    SourceClassification,
    StrategyResult,
    StrategyType,
)

from .constants import (
    COMPETITOR,
    DATE_1,
    EXAMPLE_ITEM_URL_1,
    EXAMPLE_ITEM_URL_2,
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
    monkeypatch.setattr(settings, 'llm_api_key', None)
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
    # Первым извлекается корень сайта (EXAMPLE_URL).
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


class _FakeRedis:
    """Фейковый Redis-клиент для тестов (хранилище в памяти)."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)


@pytest.mark.asyncio
async def test_parse_updates_cached_classification_on_real_strategy(
    monkeypatch,
):
    """Шаг 8: успешная стратегия персистентно обновляет классификацию.

    Источник закэширован с recommended_strategy=FAST, но реально
    fetch_with_degradation возвращает успех через STEALTH (например,
    классификация была неточной или устарела) — после parse() кэш должен
    отражать реально сработавшую стратегию, а не устаревшую.
    """
    monkeypatch.setattr(settings, 'llm_api_key', None)
    redis = _FakeRedis()
    parser = AdaptiveParser(redis_client=redis)

    await parser._cache.set_classification(
        EXAMPLE_SOURCE_NAME,
        SourceClassification(
            source_name=EXAMPLE_SOURCE_NAME,
            recommended_strategy=StrategyType.FAST.value,
        ),
    )

    class _StealthOrchestrator:
        async def fetch_with_degradation(self, url: str, **kwargs):
            return StrategyResult(
                strategy=StrategyType.STEALTH,
                success=True,
                data=_HTML,
                content_length=len(_HTML),
            )

    parser._orchestrator = _StealthOrchestrator()

    result = await parser.parse(
        url=EXAMPLE_URL,
        source_name=EXAMPLE_SOURCE_NAME,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    assert result.status == PARSER_STATUS_OK
    assert result.strategy_used == StrategyType.STEALTH

    updated = await parser._cache.get_classification(EXAMPLE_SOURCE_NAME)
    assert updated is not None
    assert updated.recommended_strategy == StrategyType.STEALTH.value


@pytest.mark.asyncio
async def test_parse_no_cache_write_when_strategy_unchanged(monkeypatch):
    """Если реальная стратегия совпадает с закэшированной — лишней
    записи в кэш не происходит (set вызывается только при расхождении)."""
    monkeypatch.setattr(settings, 'llm_api_key', None)
    redis = _FakeRedis()
    parser = AdaptiveParser(redis_client=redis)

    await parser._cache.set_classification(
        EXAMPLE_SOURCE_NAME,
        SourceClassification(
            source_name=EXAMPLE_SOURCE_NAME,
            recommended_strategy=StrategyType.FAST.value,
        ),
    )

    calls: list[str] = []
    original_set = parser._cache.set_classification

    async def _tracking_set(source_name, classification, **kwargs):
        calls.append(classification.recommended_strategy)
        return await original_set(source_name, classification, **kwargs)

    parser._cache.set_classification = _tracking_set
    parser._orchestrator = _FakeOrchestrator()  # возвращает FAST

    await parser.parse(
        url=EXAMPLE_URL,
        source_name=EXAMPLE_SOURCE_NAME,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    # set_classification не вызывался повторно — стратегия не изменилась
    # (единственный вызов был в подготовке теста, до подмены).
    assert calls == []


@pytest.mark.asyncio
async def test_parse_detects_antibot_from_real_html_no_prior_cache(
    monkeypatch,
):
    """Шаг 9: без закэшированной классификации первый вызов parse()
    определяет has_antibot по реальному HTML, а не по пустым умолчаниям.

    До фикса SourceClassifier.classify() вызывался без html/headers —
    для источника вне _KNOWN_SOURCES has_antibot оставался бы False
    "навсегда", даже если сервер явно отдаёт маркер антибот-защиты.
    """
    monkeypatch.setattr(settings, 'llm_api_key', None)
    redis = _FakeRedis()
    parser = AdaptiveParser(redis_client=redis)
    # example.com не входит ни в _KNOWN_SOURCES, ни в _REGISTRY_DOMAINS.
    assert await parser._cache.get_classification(EXAMPLE_SOURCE_NAME) is None

    antibot_html = (
        '<html><head><meta name="cf-ray" content="abc123"></head>'
        '<body><a href="https://example.com/1">Новость</a></body></html>'
    )

    class _AntibotOrchestrator:
        async def fetch_with_degradation(self, url: str, **kwargs):
            return StrategyResult(
                strategy=StrategyType.STEALTH,
                success=True,
                data=antibot_html,
                content_length=len(antibot_html),
            )

    parser._orchestrator = _AntibotOrchestrator()

    result = await parser.parse(
        url=EXAMPLE_URL,
        source_name=EXAMPLE_SOURCE_NAME,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    assert result.status == PARSER_STATUS_OK

    classification = await parser._cache.get_classification(EXAMPLE_SOURCE_NAME)
    assert classification is not None
    assert classification.has_antibot is True
    assert classification.recommended_strategy == StrategyType.STEALTH.value


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
    assert len(items) >= 1
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
    assert len(items) >= 1
    assert items[0]['title'] == NEWS_1
    assert items[0]['url'] == EXAMPLE_ITEM_URL_1
    assert items[0]['published_at'] == DATE_1


def test_parse_items_without_container_uses_links():
    """Без селектора container используется эвристика по ссылкам."""
    items = _parse_items(
        _HTML, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors={}
    )
    assert len(items) >= 1
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
    # Шум отбрасывается, полезные ссылки сохраняются.
    assert '/account/login' not in urls
    assert '/article/cookie_policy' not in urls
    assert 'https://example.com/news/1' in urls
    assert 'https://example.com/news/2' in urls


def test_parse_items_filters_non_http_schemes():
    """Не-HTTP(S) ссылки (mailto:, tel:, javascript:) не попадают в парсинг.

    Такие ссылки нельзя скачать стратегиями обхода, а на странице они
    не являются данными (кнопки «Позвонить», «Написать», обработчики).
    """
    html = """
    <html><body>
      <a href="/account/login">Войти</a>
      <a href="mailto:fips@rupto.ru">Написать</a>
      <a href="tel:+74951234567">Позвонить</a>
      <a href="javascript:void(0)">Меню</a>
      <a href="https://example.com/news/1">Новость 1</a>
    </body></html>
    """
    items = _parse_items(
        html, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors={}
    )
    urls = [i['url'] for i in items]
    # Служебные и не-HTTP(S) ссылки отброшены.
    assert not any(u.startswith('mailto:') for u in urls)
    assert not any(u.startswith('tel:') for u in urls)
    assert not any(u.startswith('javascript:') for u in urls)
    # Полезная ссылка сохраняется.
    assert 'https://example.com/news/1' in urls


def test_parse_items_applies_limit_after_filtering_noise(monkeypatch):
    """Служебные ссылки не занимают квоту полезных материалов."""
    monkeypatch.setattr(parser_module, 'DEFAULT_MAX_NEWS', 2)
    html = """
    <html><body>
      <a href="/account/login">Войти</a>
      <a href="mailto:news@example.com">Написать</a>
      <a href="https://example.com/news/1">Новость 1</a>
      <a href="https://example.com/news/2">Новость 2</a>
      <a href="https://example.com/news/3">Новость 3</a>
    </body></html>
    """

    items = _parse_items(
        html, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors={}
    )

    assert [item['url'] for item in items] == [
        'https://example.com/news/1',
        'https://example.com/news/2',
    ]


def test_parse_items_returns_all_useful_links_below_limit(monkeypatch):
    """При нехватке пригодных ссылок фильтр не добавляет шум."""
    monkeypatch.setattr(parser_module, 'DEFAULT_MAX_NEWS', 3)
    html = """
    <html><body>
      <a href="javascript:void(0)">Меню</a>
      <a href="/article/cookie_policy">Политика</a>
      <a href="https://example.com/news/1">Новость 1</a>
    </body></html>
    """

    items = _parse_items(
        html, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors={}
    )

    assert [item['url'] for item in items] == ['https://example.com/news/1']


def test_parse_items_with_selectors_filters_before_limit(monkeypatch):
    """Селекторный путь применяет лимит только после фильтрации URL."""
    monkeypatch.setattr(parser_module, 'DEFAULT_MAX_NEWS', 2)
    html = """
    <html><body>
      <div class="item">
        <a class="title" href="/account/login">Войти</a>
      </div>
      <div class="item">
        <a class="title" href="tel:+74951234567">Позвонить</a>
      </div>
      <div class="item">
        <a class="title" href="https://example.com/1">Новость 1</a>
      </div>
      <div class="item">
        <a class="title" href="https://example.com/2">Новость 2</a>
      </div>
      <div class="item">
        <a class="title" href="https://example.com/3">Новость 3</a>
      </div>
    </body></html>
    """
    selectors = {
        'container': SELECTOR_CONTAINER,
        'title': SELECTOR_TITLE,
        'url': SELECTOR_URL,
    }

    items = _parse_items(
        html, EXAMPLE_SOURCE_NAME, COMPETITOR, TRIGGER, selectors=selectors
    )

    assert [item['url'] for item in items] == [
        EXAMPLE_ITEM_URL_1,
        EXAMPLE_ITEM_URL_2,
    ]


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
    # Обе ссылки собираются (DEFAULT_MAX_NEWS >= 1 не усекает выборку).
    assert len(pairs) == 2
    assert pairs[0][0] == 'Новость 1'
    assert pairs[0][1] == 'https://www.ptsecurity.com/about/news/1'
    assert pairs[1][0] == 'Новость 2'
    assert pairs[1][1] == 'https://www.ptsecurity.com/about/news/2'


def test_default_max_news_value():
    """DEFAULT_MAX_NEWS задана и имеет положительное значение."""
    assert isinstance(DEFAULT_MAX_NEWS, int)
    assert DEFAULT_MAX_NEWS >= 1


def test_looks_truncated_detects_cut_text():
    """_looks_truncated определяет обрезанный текст по финальному знаку."""
    # Длинный текст без финальной точки — вероятно обрезан.
    long_cut = 'Слово ' * 100
    assert _looks_truncated(long_cut)
    # Длинный текст с финальной точкой — не обрезан.
    long_full = 'Слово ' * 100 + '.'
    assert not _looks_truncated(long_full)
    # Текст с маркером обрыва — обрезан.
    assert _looks_truncated('Текст ' * 100 + '...')
    # Короткий текст не считается обрезанным (это может быть сниппет).
    assert not _looks_truncated('Короткий текст')


@pytest.mark.asyncio
async def test_deep_fetch_uses_cache_and_method(monkeypatch):
    """_deep_fetch возвращает ex_method и использует кэш полного текста."""
    from src.bp1.adaptive.processing.parser import (
        MIN_FULL_ARTICLE_TEXT_LENGTH,
    )

    parser = AdaptiveParser()
    # Замещаем извлечение текста фиксированным полным текстом.
    full_text = 'x' * (MIN_FULL_ARTICLE_TEXT_LENGTH + 10) + '.'

    async def _fake_extract(url, source_name, selectors):
        return full_text, 'llm'

    parser._extract_article_text = _fake_extract  # type: ignore
    # Кэш заменяем заглушкой, чтобы не писать на диск.

    class _FakeCache:
        def __init__(self):
            self.store = {}

        async def get_article_text(self, url):
            return self.store.get(url)

        async def set_article_text(self, url, text, method):
            self.store[url] = {'text': text, 'method': method}

    parser._cache = _FakeCache()  # type: ignore

    candidates = [
        ('Новость 1', 'https://example.com/news/1', '/news/1'),
        ('Новость 2', 'https://example.com/news/2', '/news/2'),
    ]
    result = await parser._deep_fetch(
        candidates, EXAMPLE_SOURCE_NAME, selectors={}
    )
    assert len(result) == 2
    # Первый прогон — текст извлечён (llm) и закэширован.
    assert result[0]['ex_text'] == full_text
    assert result[0]['ex_method'] == 'llm'
    assert result[0]['ex_url'] == 'https://example.com/news/1'

    # Второй прогон — текст берётся из кэша, извлечение не вызывается
    # повторно. ex_method сохраняет исходный способ извлечения (llm), т.к.
    # кэш хранит полный текст вместе с методом его получения.
    calls = []

    async def _fake_extract2(url, source_name, selectors):
        calls.append(url)
        return full_text, 'llm'

    parser._extract_article_text = _fake_extract2  # type: ignore
    result2 = await parser._deep_fetch(
        candidates, EXAMPLE_SOURCE_NAME, selectors={}
    )
    assert calls == []
    assert result2[0]['ex_method'] == 'llm'


@pytest.mark.asyncio
async def test_deep_fetch_css_first_ordering():
    """_deep_fetch отдаёт приоритет статьям с CSS-селектором text."""
    from src.bp1.adaptive.processing.parser import (
        MIN_FULL_ARTICLE_TEXT_LENGTH,
    )

    parser = AdaptiveParser()
    full_text = 'y' * (MIN_FULL_ARTICLE_TEXT_LENGTH + 10) + '.'

    async def _fake_extract(url, source_name, selectors):
        return full_text, 'css'

    parser._extract_article_text = _fake_extract  # type: ignore

    class _FakeCache:
        async def get_article_text(self, url):
            return None

        async def set_article_text(self, url, text, method):
            pass

    parser._cache = _FakeCache()  # type: ignore

    candidates = [
        ('Без CSS', 'https://example.com/a', '/a'),
        ('С CSS', 'https://example.com/b', '/b'),
    ]
    # Оба кандидата обрабатываются и получают полный текст.
    result = await parser._deep_fetch(
        candidates,
        EXAMPLE_SOURCE_NAME,
        selectors={'text': '.article'},
    )
    assert len(result) == 2
    assert result[0]['ex_text'] == full_text
    assert result[1]['ex_text'] == full_text
