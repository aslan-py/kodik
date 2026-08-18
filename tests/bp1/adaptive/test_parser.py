"""Тесты для AdaptiveParser и LLMClient."""

import pytest

from core.config import settings
from src.bp1.adaptive.processing.llm import LLMClient
from src.bp1.adaptive.processing.parser import (
    ADAPTER_FAIL_THRESHOLD,
    DEFAULT_MAX_NEWS,
    MAX_PAGINATION_PAGES,
    AdaptiveParser,
    _is_ad_redirect_url,
    _is_noise_url,
    _items_per_page,
    _looks_truncated,
    _page_items,
    _pagination_url,
    _parse_items,
    _to_absolute,
)
from src.bp1.adaptive.processing.parser import constants as parser_constants
from src.bp1.adaptive.schemas import (
    AdapterState,
    ExtendedSiteClassification,
    ProbedUrl,
    QualityGateLevel,
    QualityGateReport,
    SiteType,
    SourceClassification,
    StrategyResult,
    StrategyType,
    TechnicalFeatures,
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

    # Текст ссылки упоминает COMPETITOR, иначе уровень RELEVANCE
    # DataQualityGate (change verify-search-probe-relevance) пометит
    # выдачу как не относящуюся к конкуренту — тест же проверяет
    # антибот-классификацию, а не релевантность.
    antibot_html = (
        '<html><head><meta name="cf-ray" content="abc123"></head>'
        f'<body><a href="https://example.com/1">{COMPETITOR} — новость'
        '</a></body></html>'
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


@pytest.mark.asyncio
async def test_parse_enriches_classification_via_llm(monkeypatch):
    """Шаг 10: classify_with_llm подключён к первому прогону по источнику.

    LLM детектирует антибот-защиту, которую эвристика (по ключевым словам
    в обычном _HTML без явных маркеров) не увидела бы — после первого
    parse() (адаптер ещё не создан) has_antibot в кэше становится True.
    """
    monkeypatch.setattr(settings, 'llm_api_key', None)
    redis = _FakeRedis()
    parser = AdaptiveParser(redis_client=redis)
    parser._orchestrator = _FakeOrchestrator()  # обычный _HTML, без маркеров

    async def _fake_classify_with_llm(html, url, headers=None):
        return ExtendedSiteClassification(
            source_name=url,
            site_type=SiteType.NEWS,
            confidence=0.9,
            technical_features=TechnicalFeatures(has_antibot=True),
        )

    parser._llm_client.classify_with_llm = _fake_classify_with_llm

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


@pytest.mark.asyncio
async def test_parse_llm_classify_failure_does_not_break_parse(monkeypatch):
    """Сбой LLM-категоризации не роняет parse() и не портит уже
    определённую эвристикой классификацию."""
    monkeypatch.setattr(settings, 'llm_api_key', None)
    redis = _FakeRedis()
    parser = AdaptiveParser(redis_client=redis)
    parser._orchestrator = _FakeOrchestrator()

    async def _failing_classify_with_llm(html, url, headers=None):
        raise RuntimeError('LLM timeout')

    parser._llm_client.classify_with_llm = _failing_classify_with_llm

    result = await parser.parse(
        url=EXAMPLE_URL,
        source_name=EXAMPLE_SOURCE_NAME,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    # parse() не падает, несмотря на сбой LLM.
    assert result.status == PARSER_STATUS_OK

    classification = await parser._cache.get_classification(EXAMPLE_SOURCE_NAME)
    # Классификация всё равно есть (создана эвристикой в Шагах 8-9),
    # просто без LLM-уточнения.
    assert classification is not None
    assert classification.has_antibot is False


@pytest.mark.asyncio
async def test_parse_agent_consulted_on_cold_start(monkeypatch):
    """Шаг 11: агент консультируется и без предварительной классификации
    в кэше (холодный старт), а не только когда она уже была закэширована.
    """
    monkeypatch.setattr(settings, 'llm_api_key', None)
    redis = _FakeRedis()
    parser = AdaptiveParser(redis_client=redis)
    parser._orchestrator = _FakeOrchestrator()
    assert await parser._cache.get_classification(EXAMPLE_SOURCE_NAME) is None

    calls: list[SourceClassification] = []
    original_choose = parser._agent.choose_strategy

    async def _tracking_choose(classification):
        calls.append(classification)
        return await original_choose(classification)

    parser._agent.choose_strategy = _tracking_choose

    result = await parser.parse(
        url=EXAMPLE_URL,
        source_name=EXAMPLE_SOURCE_NAME,
        competitor=COMPETITOR,
        trigger=TRIGGER,
    )
    assert result.status == PARSER_STATUS_OK
    # Агент вызван ровно один раз, даже без предварительного кэша.
    assert len(calls) == 1
    assert calls[0].source_name == EXAMPLE_SOURCE_NAME


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


def test_is_ad_redirect_url():
    """_is_ad_redirect_url отсеивает рекламные клик-редиректы hh.ru.

    Регрессионный тест: adsrv.hh.ru/click?... — рекламная ссылка на
    спонсированную вакансию, а не прямая ссылка на страницу вакансии.
    Deep-fetch такого URL скачивает страницу рекламной системы, а не саму
    вакансию.
    """
    assert _is_ad_redirect_url(
        'https://adsrv.hh.ru/click?b=2099012&place=35&clickType=link_to_vacancy'
    )
    assert not _is_ad_redirect_url(
        'https://ekaterinburg.hh.ru/vacancy/136245975?query=x'
    )
    assert not _is_ad_redirect_url('https://hh.ru/search/vacancy?text=x')
    assert not _is_ad_redirect_url('/vacancy/123')
    assert not _is_ad_redirect_url('')
    assert not _is_ad_redirect_url(None)


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
    monkeypatch.setattr(parser_constants, 'DEFAULT_MAX_NEWS', 2)
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
    monkeypatch.setattr(parser_constants, 'DEFAULT_MAX_NEWS', 3)
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
    monkeypatch.setattr(parser_constants, 'DEFAULT_MAX_NEWS', 2)
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


def test_pagination_url_offset_style():
    """Шаг 16: при известном items_per_page используется offset-стиль."""
    # Первая страница — без параметра пагинации, как и раньше.
    assert _pagination_url('https://example.com/news', 1, 20) == (
        'https://example.com/news'
    )
    # Вторая страница -> offset = (2-1) * 20.
    assert _pagination_url('https://example.com/news', 2, 20) == (
        'https://example.com/news?offset=20'
    )
    # Третья страница с уже существующим query-параметром.
    assert _pagination_url('https://example.com/news?q=ии', 3, 15) == (
        'https://example.com/news?q=ии&offset=30'
    )
    # items_per_page=0 (неизвестно) -> прежний page-стиль.
    assert _pagination_url('https://example.com/news', 2, 0) == (
        'https://example.com/news?page=2'
    )


def test_items_per_page_parsing():
    """_items_per_page устойчиво разбирает метаданные адаптера."""
    assert _items_per_page({'items_per_page': 20}) == 20
    assert _items_per_page({'items_per_page': '15'}) == 15
    assert _items_per_page({'items_per_page': 'много'}) == 0
    assert _items_per_page({'items_per_page': -5}) == 0
    assert _items_per_page({}) == 0
    assert _items_per_page(None) == 0


def test_max_pages_uses_config_limit():
    """Шаг 16: _max_pages берёт лимит из конфигурации, а не 10000."""
    parser = AdaptiveParser()
    # Без items_per_page — предел из настроек.
    assert parser._max_pages({}) == MAX_PAGINATION_PAGES


def test_max_pages_narrowed_by_items_per_page(monkeypatch):
    """При известном items_per_page лимит сужается до числа страниц,
    реально нужного, чтобы набрать DEFAULT_MAX_NEWS.

    DEFAULT_MAX_NEWS зафиксирован явным monkeypatch (чётное число), а не
    взят из реального BP1_MAX_NEWS_PER_SOURCE — тест проверяет арифметику
    _max_pages (деление пополам должно давать ровно 2 страницы), а не
    текущее значение переменной окружения; нечётное/маленькое значение из
    .env ломает именно эту арифметику (3 // 2 = 1, не половина).
    """
    monkeypatch.setattr(parser_constants, 'DEFAULT_MAX_NEWS', 4)
    parser = AdaptiveParser()
    # На странице столько же элементов, сколько нужно всего -> 1 страница.
    assert parser._max_pages({'items_per_page': 4}) == 1
    # Вдвое меньше на странице -> нужно 2 страницы.
    assert parser._max_pages({'items_per_page': 2}) == 2
    # Огромная страница -> всё равно минимум 1.
    assert parser._max_pages({'items_per_page': 10_000}) == 1


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


def test_page_items_collects_from_all_containers():
    """_page_items (эвристическая ветка) собирает ссылки со ВСЕХ карточек.

    Регрессионный тест: раньше soup.select_one(container) брал только
    первую карточку из N на странице листинга, из-за чего терялись почти
    все новости (например, lenta.ru отдавал 1 новость вместо 10). Адаптер
    задаёт container, но НЕ задаёт url/title — код должен уйти в
    эвристическую ветку и всё равно собрать ссылки со всех карточек.
    """
    html = """
    <html><body>
      <div class="card"><a href="/news/1">Новость 1</a></div>
      <div class="card"><a href="/news/2">Новость 2</a></div>
      <div class="card"><a href="/news/3">Новость 3</a></div>
    </body></html>
    """
    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={'container': 'div.card'},
        base_url='https://example.com/',
    )
    assert len(pairs) == 3
    assert [p[0] for p in pairs] == ['Новость 1', 'Новость 2', 'Новость 3']
    assert [p[1] for p in pairs] == [
        'https://example.com/news/1',
        'https://example.com/news/2',
        'https://example.com/news/3',
    ]


def test_page_items_explodes_list_container_with_field_selectors():
    """_page_items (ветка с url/title-селекторами) раскладывает

    контейнер-список на отдельные записи.

    Регрессионный тест на реальный инцидент: у hh.ru/lenta.ru LLM-анализ
    вернул ``container``, указывающий на ОБЁРТКУ списка целиком
    (``ol.vacancies-list``/``ul.search-results__list``), а не на карточку
    одной записи. ``soup.select(container)`` находит ровно один такой
    элемент — раньше внутри него бралось только первое совпадение title/url
    (``select_one``), и вместо 10 вакансий/новостей оставалась 1.
    """
    html = """
    <html><body>
      <ul class="list">
        <li>
          <h3 class="title">Новость 1</h3>
          <a class="link" href="/news/1">x</a>
        </li>
        <li>
          <h3 class="title">Новость 2</h3>
          <a class="link" href="/news/2">x</a>
        </li>
        <li>
          <h3 class="title">Новость 3</h3>
          <a class="link" href="/news/3">x</a>
        </li>
      </ul>
    </body></html>
    """
    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={
            'container': 'ul.list',
            'title': 'h3.title',
            'url': 'a.link',
        },
        base_url='https://example.com/',
    )
    assert len(pairs) == 3
    assert [p[0] for p in pairs] == ['Новость 1', 'Новость 2', 'Новость 3']
    assert [p[1] for p in pairs] == [
        'https://example.com/news/1',
        'https://example.com/news/2',
        'https://example.com/news/3',
    ]


def test_page_items_propagates_published_at_region_media_name():
    """_page_items прокидывает published_at/region/media_name с листинга.

    Раньше эти поля извлекались _extract_by_selectors, но _page_items
    возвращал только (title, url) — данные терялись на этой границе.
    """
    html = """
    <html><body>
      <div class="card">
        <h3 class="title">Новость 1</h3>
        <a class="link" href="/news/1">x</a>
        <span class="date">18.07.2026</span>
        <span class="region">г. Москва</span>
        <span class="media">РБК</span>
      </div>
    </body></html>
    """
    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={
            'container': 'div.card',
            'title': 'h3.title',
            'url': 'a.link',
            'published_at': 'span.date',
            'region': 'span.region',
            'media_name': 'span.media',
        },
        base_url='https://example.com/',
    )
    assert len(pairs) == 1
    _title, _url_abs, _url_rel, published_at, region, media_name = pairs[0]
    assert published_at == '18.07.2026'
    assert region == 'г. Москва'
    assert media_name == 'РБК'


def test_page_items_missing_fields_stay_none():
    """Без селекторов published_at/region/media_name — не выдумываем None."""
    html = """
    <html><body>
      <div class="card">
        <h3 class="title">Новость 1</h3>
        <a class="link" href="/news/1">x</a>
      </div>
    </body></html>
    """
    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={
            'container': 'div.card',
            'title': 'h3.title',
            'url': 'a.link',
        },
        base_url='https://example.com/',
    )
    assert len(pairs) == 1
    _title, _url_abs, _url_rel, published_at, region, media_name = pairs[0]
    assert published_at is None
    assert region is None
    assert media_name is None


def test_page_items_single_item_container_unaffected():
    """Обычный случай (контейнер = одна карточка) не ломается доработкой.

    Каждый селектор поля находит не больше одного совпадения внутри своего
    контейнера — поведение должно остаться прежним (по одной записи на
    контейнер), даже если на странице несколько таких контейнеров.
    """
    html = """
    <html><body>
      <div class="card">
        <h3 class="title">Новость 1</h3>
        <a class="link" href="/news/1">x</a>
      </div>
      <div class="card">
        <h3 class="title">Новость 2</h3>
        <a class="link" href="/news/2">x</a>
      </div>
    </body></html>
    """
    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={
            'container': 'div.card',
            'title': 'h3.title',
            'url': 'a.link',
        },
        base_url='https://example.com/',
    )
    assert len(pairs) == 2
    assert [p[0] for p in pairs] == ['Новость 1', 'Новость 2']


def test_page_items_prefers_title_own_href_over_unrelated_links():
    """Заголовок-ссылка не путается с посторонними ссылками внутри карточки.

    Регрессионный тест на реальный инцидент (hh.ru): внутри ОДНОЙ карточки
    вакансии может быть несколько разных `<a href>` (реклама, работодатель,
    кнопка отклика) помимо самой ссылки на вакансию. Широкий `url`-селектор
    (`a[href]`) матчит их все — при сопоставлении по голому индексу
    совпадения (title[i] с url[i]) число совпадений на поле расходится, и
    заголовок одной карточки приклеивается к ссылке постороннего элемента
    (в том числе из ДРУГОЙ карточки). Заголовок сам является ссылкой —
    его собственный href должен побеждать независимый поиск по контейнеру.
    """
    html = """
    <html><body>
      <article class="card">
        <a class="noise" href="/ad/1">реклама</a>
        <a class="title" href="/vacancy/1">Вакансия 1</a>
        <a class="noise" href="/employer/1">работодатель</a>
      </article>
      <article class="card">
        <a class="noise" href="/ad/2">реклама</a>
        <a class="title" href="/vacancy/2">Вакансия 2</a>
        <a class="noise" href="/employer/2">работодатель</a>
      </article>
    </body></html>
    """
    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={
            'container': 'article.card',
            'title': 'a.title',
            'url': 'a[href]',
        },
        base_url='https://example.com/',
    )
    assert len(pairs) == 2
    assert pairs[0][0] == 'Вакансия 1'
    assert pairs[0][1] == 'https://example.com/vacancy/1'
    assert pairs[1][0] == 'Вакансия 2'
    assert pairs[1][1] == 'https://example.com/vacancy/2'


def test_page_items_finds_card_link_outside_title_scope():
    """URL карточки может находиться над вложенным заголовком."""
    html = """
    <html><body>
      <div class="result">
        <div class="card">
          <a class="overlay" href="/about/news/one"></a>
          <div class="content"><h3>News 1</h3></div>
        </div>
      </div>
    </body></html>
    """

    pairs = _page_items(
        html,
        EXAMPLE_SOURCE_NAME,
        COMPETITOR,
        TRIGGER,
        selectors={
            'container': 'div.result',
            'title': 'h3',
            'url': 'a[href]',
        },
        base_url='https://example.com/',
    )

    assert pairs == [
        (
            'News 1',
            'https://example.com/about/news/one',
            '/about/news/one',
            None,
            None,
            None,
        )
    ]


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


# ============================================================================
# Best-of каскад _extract_article_text: не должен стопориться на коротком
# CSS/readability-результате, если LLM может дать более полный текст.
# ============================================================================


class _ArticleOrchestrator:
    """Оркестратор-заглушка, возвращающая фиксированный HTML статьи."""

    def __init__(self, html: str):
        self._html = html

    async def fetch_with_degradation(self, url: str, **kwargs):
        return StrategyResult(
            strategy=StrategyType.FAST,
            success=True,
            data=self._html,
            content_length=len(self._html),
        )


@pytest.mark.asyncio
async def test_extract_article_text_escalates_short_css_to_llm(monkeypatch):
    """Короткий CSS-результат (лид-абзац) не глушит каскад — LLM пробуется.

    Регрессионный тест на исходную проблему: CSS-селектор, зацепивший
    только первые 100+ символов статьи, раньше останавливал каскад и не
    давал шанса извлечь полный текст через LLM.
    """
    from src.bp1.adaptive.processing.parser import (
        MIN_ARTICLE_TEXT_LENGTH,
        MIN_FULL_ARTICLE_TEXT_LENGTH,
    )

    lead_paragraph = 'Лид. ' * (MIN_ARTICLE_TEXT_LENGTH // 5)
    assert (
        MIN_ARTICLE_TEXT_LENGTH
        <= len(lead_paragraph)
        < (MIN_FULL_ARTICLE_TEXT_LENGTH)
    )
    html = (
        f'<html><body><div class="content">{lead_paragraph}</div></body></html>'
    )
    full_text = 'x' * (MIN_FULL_ARTICLE_TEXT_LENGTH + 50) + '.'

    parser = AdaptiveParser()
    parser._orchestrator = _ArticleOrchestrator(html)

    async def _fake_llm_extract(html_arg):
        return full_text, {'chunked': False, 'chunks_dropped': 0}

    parser._llm_extract_text_with_meta = _fake_llm_extract  # type: ignore

    text, method, meta = await parser._extract_article_text(
        'https://example.com/news/1',
        EXAMPLE_SOURCE_NAME,
        selectors={'text': '.content'},
    )
    assert method == 'llm'
    assert text == full_text
    assert meta['complete'] is True


@pytest.mark.asyncio
async def test_extract_article_text_confident_css_skips_llm(monkeypatch):
    """Уверенно полный CSS-результат не тратит LLM-вызов."""
    from src.bp1.adaptive.processing.parser import (
        MIN_FULL_ARTICLE_TEXT_LENGTH,
    )

    full_text = 'y' * (MIN_FULL_ARTICLE_TEXT_LENGTH + 50) + '.'
    html = f'<html><body><div class="content">{full_text}</div></body></html>'

    parser = AdaptiveParser()
    parser._orchestrator = _ArticleOrchestrator(html)

    calls: list[str] = []

    async def _fake_llm_extract(html_arg):
        calls.append(html_arg)
        return 'не должно вызываться', {'chunked': False, 'chunks_dropped': 0}

    parser._llm_extract_text_with_meta = _fake_llm_extract  # type: ignore

    text, method, meta = await parser._extract_article_text(
        'https://example.com/news/1',
        EXAMPLE_SOURCE_NAME,
        selectors={'text': '.content'},
    )
    assert method == 'css'
    assert text == full_text
    assert meta['complete'] is True
    assert calls == []  # LLM не вызывался — CSS уже уверенно полный.


@pytest.mark.asyncio
async def test_extract_article_text_snippet_page_when_nothing_matches():
    """Без CSS-селектора и без LLM — сниппет всей страницы (snippet_page)."""
    html = (
        '<html><body><p>Просто текст страницы без разметки статьи.</p>'
        '</body></html>'
    )

    parser = AdaptiveParser()
    parser._orchestrator = _ArticleOrchestrator(html)

    async def _fake_llm_extract(html_arg):
        return None, {'chunked': False, 'chunks_dropped': 0}

    parser._llm_extract_text_with_meta = _fake_llm_extract  # type: ignore

    text, method, meta = await parser._extract_article_text(
        'https://example.com/news/1',
        EXAMPLE_SOURCE_NAME,
        selectors={},
    )
    assert method == 'snippet_page'
    assert text and 'Просто текст страницы' in text
    assert meta['complete'] is False


@pytest.mark.asyncio
async def test_extract_article_text_not_fetchable_returns_snippet_title():
    """Не-HTTP(S) ссылки сразу дают snippet_title без похода в сеть."""
    parser = AdaptiveParser()

    text, method, meta = await parser._extract_article_text(
        'mailto:info@example.com',
        EXAMPLE_SOURCE_NAME,
        selectors={},
    )
    assert text is None
    assert method == 'snippet_title'
    assert meta['complete'] is False


class _RecordingOrchestrator:
    """Оркестратор-заглушка, фиксирующая kwargs каждого вызова."""

    def __init__(self, html: str):
        self._html = html
        self.calls: list[dict] = []

    async def fetch_with_degradation(self, url: str, **kwargs):
        self.calls.append(kwargs)
        return StrategyResult(
            strategy=StrategyType.FAST,
            success=True,
            data=self._html,
            content_length=len(self._html),
        )


@pytest.mark.asyncio
async def test_extract_article_text_reuses_listing_strategy():
    """Deep-fetch статьи стартует с уже известной стратегии листинга.

    Регрессионный тест: раньше deep-fetch не передавал start_with/
    classification в fetch_with_degradation и каждая статья заново вслепую
    перебирала всю цепочку деградации — из-за этого почти всегда не
    укладывалась в ARTICLE_FETCH_TIMEOUT_SECONDS и скатывалась в
    snippet_title, даже когда рабочая стратегия для источника уже известна.
    """
    html = '<html><body><p>x</p></body></html>'
    orchestrator = _RecordingOrchestrator(html)
    parser = AdaptiveParser()
    parser._orchestrator = orchestrator

    classification = SourceClassification(
        source_name=EXAMPLE_SOURCE_NAME,
        recommended_strategy='STEALTH',
        has_antibot=True,
    )
    await parser._extract_article_text(
        'https://example.com/news/1',
        EXAMPLE_SOURCE_NAME,
        selectors={},
        start_with=StrategyType.STEALTH,
        classification=classification,
    )
    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0]['start_with'] == StrategyType.STEALTH
    assert orchestrator.calls[0]['classification'] is classification


@pytest.mark.asyncio
async def test_deep_fetch_propagates_start_with_and_classification():
    """_deep_fetch прокидывает start_with/classification дальше в вызов."""
    parser = AdaptiveParser()

    class _FakeCache:
        async def get_article_text(self, url):
            return None

        async def set_article_text(
            self, url, text, method, possibly_incomplete=False, ttl=None
        ):
            pass

    parser._cache = _FakeCache()  # type: ignore

    received: list[dict] = []

    async def _fake_extract(url, source_name, selectors, **kwargs):
        received.append(kwargs)
        return 'text', 'css', {'complete': True, 'chunks_dropped': 0}

    parser._extract_article_text = _fake_extract  # type: ignore

    classification = SourceClassification(
        source_name=EXAMPLE_SOURCE_NAME,
        recommended_strategy='CRAWL4AI',
        has_antibot=False,
    )
    await parser._deep_fetch(
        [
            (
                'Новость',
                'https://example.com/news/1',
                '/news/1',
                None,
                None,
                None,
            )
        ],
        EXAMPLE_SOURCE_NAME,
        selectors={},
        start_with=StrategyType.CRAWL4AI,
        classification=classification,
    )
    assert len(received) == 1
    assert received[0]['start_with'] == StrategyType.CRAWL4AI
    assert received[0]['classification'] is classification


@pytest.mark.asyncio
async def test_deep_fetch_uses_cache_and_method(monkeypatch):
    """_deep_fetch возвращает ex_method и использует кэш полного текста."""
    from src.bp1.adaptive.processing.parser import (
        MIN_FULL_ARTICLE_TEXT_LENGTH,
    )

    parser = AdaptiveParser()
    # Замещаем извлечение текста фиксированным полным текстом.
    full_text = 'x' * (MIN_FULL_ARTICLE_TEXT_LENGTH + 10) + '.'

    async def _fake_extract(url, source_name, selectors, **kwargs):
        return full_text, 'llm', {'complete': True, 'chunks_dropped': 0}

    parser._extract_article_text = _fake_extract  # type: ignore
    # Кэш заменяем заглушкой, чтобы не писать на диск.

    class _FakeCache:
        def __init__(self):
            self.store = {}

        async def get_article_text(self, url):
            return self.store.get(url)

        async def set_article_text(
            self, url, text, method, possibly_incomplete=False, ttl=None
        ):
            self.store[url] = {
                'text': text,
                'method': method,
                'possibly_incomplete': possibly_incomplete,
            }

    parser._cache = _FakeCache()  # type: ignore

    candidates = [
        (
            'Новость 1',
            'https://example.com/news/1',
            '/news/1',
            None,
            None,
            None,
        ),
        (
            'Новость 2',
            'https://example.com/news/2',
            '/news/2',
            None,
            None,
            None,
        ),
    ]
    result = await parser._deep_fetch(
        candidates, EXAMPLE_SOURCE_NAME, selectors={}
    )
    assert len(result) == 2
    # Первый прогон — текст извлечён (llm) и закэширован.
    assert result[0]['ex_text'] == full_text
    assert result[0]['ex_method'] == 'llm'
    assert result[0]['ex_url'] == 'https://example.com/news/1'
    assert result[0]['ex_text_length'] == len(full_text)
    assert result[0]['ex_text_possibly_incomplete'] is False

    # Второй прогон — текст берётся из кэша, извлечение не вызывается
    # повторно. ex_method сохраняет исходный способ извлечения (llm), т.к.
    # кэш хранит полный текст вместе с методом его получения.
    calls = []

    async def _fake_extract2(url, source_name, selectors, **kwargs):
        calls.append(url)
        return full_text, 'llm', {'complete': True, 'chunks_dropped': 0}

    parser._extract_article_text = _fake_extract2  # type: ignore
    result2 = await parser._deep_fetch(
        candidates, EXAMPLE_SOURCE_NAME, selectors={}
    )
    assert calls == []
    assert result2[0]['ex_method'] == 'llm'


@pytest.mark.asyncio
async def test_deep_fetch_adds_listing_fields_when_present():
    """_deep_fetch добавляет ex_published_at/ex_region/ex_media_name,

    когда они пришли с листинга (_page_items), и не добавляет ключи, если
    значения нет — без LLM-обогащения.
    """
    parser = AdaptiveParser()

    async def _fake_extract(url, source_name, selectors, **kwargs):
        return 'текст', 'css', {'complete': True, 'chunks_dropped': 0}

    parser._extract_article_text = _fake_extract  # type: ignore

    class _FakeCache:
        async def get_article_text(self, url):
            return None

        async def set_article_text(
            self, url, text, method, possibly_incomplete=False, ttl=None
        ):
            pass

    parser._cache = _FakeCache()  # type: ignore

    candidates = [
        (
            'С полями',
            'https://example.com/a',
            '/a',
            '18.07.2026',
            'г. Москва',
            'РБК',
        ),
        ('Без полей', 'https://example.com/b', '/b', None, None, None),
    ]
    result = await parser._deep_fetch(
        candidates, EXAMPLE_SOURCE_NAME, selectors={}
    )
    assert len(result) == 2
    assert result[0]['ex_published_at'] == '18.07.2026'
    assert result[0]['ex_region'] == 'г. Москва'
    assert result[0]['ex_media_name'] == 'РБК'
    assert 'ex_published_at' not in result[1]
    assert 'ex_region' not in result[1]
    assert 'ex_media_name' not in result[1]


@pytest.mark.asyncio
async def test_deep_fetch_css_first_ordering():
    """_deep_fetch отдаёт приоритет статьям с CSS-селектором text."""
    from src.bp1.adaptive.processing.parser import (
        MIN_FULL_ARTICLE_TEXT_LENGTH,
    )

    parser = AdaptiveParser()
    full_text = 'y' * (MIN_FULL_ARTICLE_TEXT_LENGTH + 10) + '.'

    async def _fake_extract(url, source_name, selectors, **kwargs):
        return full_text, 'css', {'complete': True, 'chunks_dropped': 0}

    parser._extract_article_text = _fake_extract  # type: ignore

    class _FakeCache:
        async def get_article_text(self, url):
            return None

        async def set_article_text(
            self, url, text, method, possibly_incomplete=False, ttl=None
        ):
            pass

    parser._cache = _FakeCache()  # type: ignore

    candidates = [
        ('Без CSS', 'https://example.com/a', '/a', None, None, None),
        ('С CSS', 'https://example.com/b', '/b', None, None, None),
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


# ============================================================================
# Шаг 21: самокоррекция адаптера по итогам Quality Gate (N6)
# ============================================================================


def _cached_adapter(fail_count: int = 0) -> AdapterState:
    return AdapterState(
        source_name=EXAMPLE_SOURCE_NAME,
        selectors={'container': '.item', 'title': '.t', 'url': 'a'},
        confidence=0.9,
        fail_count=fail_count,
    )


@pytest.mark.asyncio
async def test_quality_failure_increments_adapter_fail_count():
    """Первый провал качества не сбрасывает адаптер, а считает попытку."""
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter()
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)

    review = await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=True,
        quality_ok=False,
        items=[],
        html='<html></html>',
    )

    assert review is None
    stored = await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME)
    assert stored is not None, 'адаптер не должен сбрасываться с первого раза'
    assert stored.fail_count == 1


@pytest.mark.asyncio
async def test_quality_failure_resets_adapter_at_threshold():
    """По достижении порога адаптер сбрасывается и запрашивается разбор."""
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter(fail_count=ADAPTER_FAIL_THRESHOLD - 1)
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)

    called: list[str] = []

    async def _fake_analyze(html, items, source_name):
        called.append(source_name)
        return {'recommendation': 'селекторы устарели', 'confidence': 0.8}

    parser._agent.analyze_result = _fake_analyze

    review = await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=True,
        quality_ok=False,
        items=[],
        html='<html></html>',
    )

    assert called == [EXAMPLE_SOURCE_NAME]
    assert review == {'recommendation': 'селекторы устарели', 'confidence': 0.8}
    # Адаптер удалён — на следующем прогоне селекторы выведутся заново.
    assert await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME) is None


@pytest.mark.asyncio
async def test_quality_success_resets_fail_counter():
    """Успешное качество обнуляет накопленные провалы."""
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter(fail_count=1)
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)

    await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=True,
        quality_ok=True,
        items=[],
        html='<html></html>',
    )

    stored = await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME)
    assert stored is not None
    assert stored.fail_count == 0


@pytest.mark.asyncio
async def test_fresh_adapter_not_penalised_on_quality_failure():
    """Свежесозданный адаптер не сбрасывается и не штрафуется.

    Иначе он удалялся бы в том же прогоне, в котором был выведен, —
    бесконечная пересборка без накопления опыта.
    """
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter()
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)

    review = await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=False,
        quality_ok=False,
        items=[],
        html='<html></html>',
    )

    assert review is None
    stored = await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME)
    assert stored is not None
    assert stored.fail_count == 0


@pytest.mark.asyncio
async def test_adapter_reset_survives_llm_failure():
    """Сбой LLM-разбора не мешает сбросить устаревший адаптер."""
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter(fail_count=ADAPTER_FAIL_THRESHOLD - 1)
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)

    async def _failing_analyze(html, items, source_name):
        raise RuntimeError('LLM down')

    parser._agent.analyze_result = _failing_analyze

    review = await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=True,
        quality_ok=False,
        items=[],
        html='<html></html>',
    )

    assert review is None
    assert await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME) is None


# ============================================================================
# verify-search-probe-relevance: сброс probed_url при повторном провале
# именно уровня RELEVANCE
# ============================================================================


def _reports(*, relevance_passed: bool) -> list[QualityGateReport]:
    """Набор отчётов Quality Gate с заданным исходом уровня RELEVANCE."""
    return [
        QualityGateReport(level=QualityGateLevel.SCHEMA, passed=True),
        QualityGateReport(
            level=QualityGateLevel.RELEVANCE,
            passed=relevance_passed,
            errors=[] if relevance_passed else ['не найдено упоминаний'],
        ),
    ]


@pytest.mark.asyncio
async def test_relevance_failure_at_threshold_also_clears_probed_url():
    """Повторный провал именно RELEVANCE сбрасывает и адаптер, и

    закэшированный поисковый URL для этой пары (источник+search_param) —
    регресс-тест на инцидент rbc.ru (найденный поисковый URL перестал
    относиться к конкуренту, но переживал сброс одних селекторов).
    """
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter(fail_count=ADAPTER_FAIL_THRESHOLD - 1)
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)
    await parser._cache.set_probed_url(
        EXAMPLE_SOURCE_NAME,
        ProbedUrl(
            source_name=EXAMPLE_SOURCE_NAME,
            search_url='https://example.com/search?q=stale',
        ),
        search_param=COMPETITOR,
    )

    await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=True,
        quality_ok=False,
        items=[],
        html='<html></html>',
        reports=_reports(relevance_passed=False),
        search_param=COMPETITOR,
    )

    assert await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME) is None
    assert (
        await parser._cache.get_probed_url(
            EXAMPLE_SOURCE_NAME, search_param=COMPETITOR
        )
        is None
    )


@pytest.mark.asyncio
async def test_other_level_failure_does_not_clear_probed_url():
    """Повторный провал уровня, ОТЛИЧНОГО от RELEVANCE (например, SCHEMA),

    сбрасывает только адаптер — найденный поисковый URL остаётся, как и
    раньше (Шаг 21 прежнего рефакторинга).
    """
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter(fail_count=ADAPTER_FAIL_THRESHOLD - 1)
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)
    probed = ProbedUrl(
        source_name=EXAMPLE_SOURCE_NAME,
        search_url='https://example.com/search?q=ok',
    )
    await parser._cache.set_probed_url(
        EXAMPLE_SOURCE_NAME, probed, search_param=COMPETITOR
    )

    await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=True,
        quality_ok=False,
        items=[],
        html='<html></html>',
        reports=_reports(relevance_passed=True),
        search_param=COMPETITOR,
    )

    assert await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME) is None
    still_cached = await parser._cache.get_probed_url(
        EXAMPLE_SOURCE_NAME, search_param=COMPETITOR
    )
    assert still_cached is not None
    assert still_cached.search_url == 'https://example.com/search?q=ok'


@pytest.mark.asyncio
async def test_relevance_failure_below_threshold_clears_nothing():
    """Единичный провал RELEVANCE (не достигший порога) — ничего не

    сбрасывается, только инкремент fail_count (как для остальных
    уровней).
    """
    parser = AdaptiveParser(redis_client=_FakeRedis())
    adapter = _cached_adapter()  # fail_count=0
    await parser._cache.set_adapter(EXAMPLE_SOURCE_NAME, adapter)
    probed = ProbedUrl(
        source_name=EXAMPLE_SOURCE_NAME,
        search_url='https://example.com/search?q=ok',
    )
    await parser._cache.set_probed_url(
        EXAMPLE_SOURCE_NAME, probed, search_param=COMPETITOR
    )

    review = await parser._handle_quality_outcome(
        source_name=EXAMPLE_SOURCE_NAME,
        adapter=adapter,
        adapter_from_cache=True,
        quality_ok=False,
        items=[],
        html='<html></html>',
        reports=_reports(relevance_passed=False),
        search_param=COMPETITOR,
    )

    assert review is None
    stored = await parser._cache.get_adapter(EXAMPLE_SOURCE_NAME)
    assert stored is not None and stored.fail_count == 1
    still_cached = await parser._cache.get_probed_url(
        EXAMPLE_SOURCE_NAME, search_param=COMPETITOR
    )
    assert still_cached is not None
