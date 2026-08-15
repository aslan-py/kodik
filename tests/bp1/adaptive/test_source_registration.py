"""Тесты регистрации источников (SourceRegistrationService)."""

import pytest
from sqlalchemy import select

from src.bp1.adaptive.integration.sources import (
    SearchParamResolver,
    SearchUrlTemplateRegistry,
    SourceRegistrationService,
    build_search_url,
    extract_host,
    normalize_source_url,
)
from src.bp1.adaptive.schemas import (
    ProbedUrl,
    SourceClassification,
    SourceType,
)
from src.bp1.models import Source

from .constants import (
    COMPETITOR_INN,
    SEARCH_QUERY,
    SEARCH_URL,
    SEARCH_URL_FEDRESURS_INN,
    SEARCH_URL_HH,
    SEARCH_URL_HH_QUERY,
    SRC_API_HH,
    SRC_API_HH_HOST,
    SRC_EMPTY,
    SRC_FEDRESURS_HOST,
    SRC_FEDRESURS_PORT,
    SRC_HH_HOST,
    SRC_INVALID_REF,
    SRC_LENTA_HOST,
    SRC_LENTA_NEWS,
    SRC_LENTA_NORMALIZED,
    SRC_LENTA_UPPER,
    SRC_LENTA_WWW,
    SRC_TEST_NEWS_HOST,
    SRC_TEST_NEWS_NORMALIZED,
    SRC_TEST_NEWS_URL,
    SRC_WHITESPACE,
    SRC_ZH,
    TEST_NEWS_REDIS_CLASSIFICATION_KEY,
)


class _FakeRedis:
    """Фейковый Redis-клиент для тестов (in-memory)."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)


# ============================================================================
# extract_host / normalize_source_url / build_search_url
# ============================================================================


@pytest.mark.parametrize(
    ('url', 'expected'),
    [
        (SRC_LENTA_WWW, SRC_LENTA_HOST),
        (SRC_API_HH, SRC_API_HH_HOST),
        (SRC_FEDRESURS_PORT, SRC_FEDRESURS_HOST),
        (SRC_LENTA_UPPER, SRC_LENTA_HOST),
        (SRC_LENTA_HOST, SRC_LENTA_HOST),
    ],
)
def test_extract_host_variants(url, expected):
    assert extract_host(url) == expected


@pytest.mark.parametrize('bad', [SRC_INVALID_REF, SRC_EMPTY, SRC_WHITESPACE])
def test_extract_host_invalid(bad):
    with pytest.raises(ValueError):
        extract_host(bad)


def test_normalize_source_url():
    assert normalize_source_url(SRC_LENTA_WWW) == SRC_LENTA_NORMALIZED


@pytest.mark.parametrize(
    ('source_name', 'expected'),
    [
        (SRC_LENTA_NORMALIZED, SEARCH_URL),
        (SRC_LENTA_HOST, SEARCH_URL),
        (SRC_LENTA_NEWS, SEARCH_URL),
    ],
)
def test_build_search_url(source_name, expected):
    assert build_search_url(source_name, SEARCH_QUERY) == expected


# ============================================================================
# SearchUrlTemplateRegistry (per-source шаблоны URL поиска)
# ============================================================================


def test_build_search_url_uses_per_source_template_hh():
    """Для hh.ru используется специфичный шаблон /search/vacancy?text=."""
    registry = SearchUrlTemplateRegistry()
    url = registry.build_url(SRC_HH_HOST, SEARCH_URL_HH_QUERY)
    assert url == SEARCH_URL_HH


def test_build_search_url_uses_registry_template_for_inn():
    """Для гос. источника (fedresurs) шаблон строится с ИНН."""
    registry = SearchUrlTemplateRegistry()
    url = registry.build_url(SRC_FEDRESURS_HOST, COMPETITOR_INN)
    assert url == SEARCH_URL_FEDRESURS_INN


def test_build_search_url_fallback_to_default_template():
    """Для неизвестного источника используется универсальный /search?q=."""
    registry = SearchUrlTemplateRegistry()
    url = registry.build_url(SRC_LENTA_HOST, SEARCH_QUERY)
    assert url == SEARCH_URL


def test_registry_custom_templates_injected():
    """Пользовательские шаблоны переопределяют дефолтный реестр."""
    registry = SearchUrlTemplateRegistry(
        templates={'example.com': '/find?x={q}'}
    )
    assert registry.resolve('https://example.com/') == '/find?x={q}'


# ============================================================================
# SearchParamResolver (source-aware выбор ИНН vs название)
# ============================================================================


def _classification(
    source_type: SourceType = SourceType.UNKNOWN,
    site_type=None,
) -> SourceClassification:
    """Строит SourceClassification с опциональным site_type в metadata."""
    cls = SourceClassification(source_name='src', source_type=source_type)
    if site_type is not None:
        cls.site_type = site_type
    return cls


def test_resolver_prefers_inn_for_registry_source_type():
    """SourceType.REGISTRY -> поиск по ИНН."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.REGISTRY)
    param = resolver.resolve(
        SRC_FEDRESURS_HOST, COMPETITOR_INN, 'ООО', 'x', cls
    )
    assert param == COMPETITOR_INN


def test_resolver_prefers_inn_for_known_gov_domain_without_classification():
    """Госдомен из _REGISTRY_INN_DOMAINS -> ИНН даже без классификации."""
    resolver = SearchParamResolver()
    param = resolver.resolve(SRC_ZH, COMPETITOR_INN, 'ООО', 'x', None)
    assert param == COMPETITOR_INN


def test_resolver_uses_name_for_news_source():
    """Обычный источник -> название конкурента (competitor.name)."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.NEWS)
    param = resolver.resolve(
        SRC_LENTA_HOST, COMPETITOR_INN, 'ООО АРХИТЕХ ИИ', 'Москва', cls
    )
    assert param == 'ООО АРХИТЕХ ИИ'


def test_resolver_uses_name_even_when_trigger_present():
    """На не-гос. источнике приоритет у competitor.name, а не у trigger."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.NEWS)
    param = resolver.resolve(SRC_LENTA_HOST, None, 'ООО Кодик', 'Москва', cls)
    assert param == 'ООО Кодик'


def test_resolver_falls_back_to_trigger_when_no_competitor():
    """Без названия конкурента на не-гос. источнике используется триггер."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.NEWS)
    param = resolver.resolve(SRC_LENTA_HOST, None, None, 'Москва', cls)
    assert param == 'Москва'


def test_resolver_falls_back_to_name_for_gov_when_no_inn():
    """Гос. источник без ИНН -> fallback на название конкурента (не падает)."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.REGISTRY)
    param = resolver.resolve(SRC_FEDRESURS_HOST, None, 'ООО', 'x', cls)
    assert param == 'ООО'


def test_missing_inn_true_for_gov_without_inn():
    """Гос. источник без ИНН -> missing_inn=True (нужен пропуск)."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.REGISTRY)
    assert resolver.missing_inn(SRC_FEDRESURS_HOST, None, 'x', cls) is True


def test_missing_inn_false_for_gov_with_inn():
    """Гос. источник с ИНН -> missing_inn=False (поиск выполняется)."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.REGISTRY)
    assert (
        resolver.missing_inn(SRC_FEDRESURS_HOST, COMPETITOR_INN, 'x', cls)
        is False
    )


def test_missing_inn_false_when_trigger_is_inn():
    """Гос. источник без competitor_inn, но trigger — ИНН -> не пропуск."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.REGISTRY)
    assert (
        resolver.missing_inn(SRC_FEDRESURS_HOST, None, COMPETITOR_INN, cls)
        is False
    )


def test_missing_inn_false_for_non_gov_source():
    """Не-гос. источник не требует ИНН (поиск по названию)."""
    resolver = SearchParamResolver()
    cls = _classification(source_type=SourceType.NEWS)
    assert resolver.missing_inn(SRC_LENTA_HOST, None, 'x', cls) is False


# ============================================================================
# SourceRegistrationService.register
# ============================================================================


@pytest.mark.asyncio
async def test_register_creates_source(session):
    """Регистрация создаёт Source и кэширует классификацию в Redis."""
    fake_redis = _FakeRedis()
    service = SourceRegistrationService(session, redis_client=fake_redis)

    result = await service.register(SRC_TEST_NEWS_URL, fake_redis)

    assert result.created is True
    assert result.source_name == SRC_TEST_NEWS_NORMALIZED
    assert result.host == SRC_TEST_NEWS_HOST
    assert result.classification.source_type == SourceType.NEWS

    # В БД появилась запись Source.
    source = (
        await session.execute(
            select(Source).where(Source.name == SRC_TEST_NEWS_NORMALIZED)
        )
    ).scalar_one_or_none()
    assert source is not None
    assert source.id == result.source_id

    # В Redis появился ключ классификации.
    assert fake_redis._store.get(TEST_NEWS_REDIS_CLASSIFICATION_KEY) is not None


@pytest.mark.asyncio
async def test_register_is_idempotent(session):
    """Повторная регистрация не создаёт дубль, возвращает created=False."""
    fake_redis = _FakeRedis()
    service = SourceRegistrationService(session, redis_client=fake_redis)

    first = await service.register(SRC_TEST_NEWS_NORMALIZED, fake_redis)
    second = await service.register(SRC_TEST_NEWS_URL, fake_redis)

    assert first.created is True
    assert second.created is False
    assert second.source_id == first.source_id

    count = (
        await session.execute(
            select(Source).where(Source.name == SRC_TEST_NEWS_NORMALIZED)
        )
    ).scalar_one_or_none()
    assert count is not None


# ============================================================================
# Шаг 19: проверка поискового эндпоинта при регистрации источника
# ============================================================================


class _FakeSession:
    """Заглушка AsyncSession: источник всегда "новый"."""

    def __init__(self):
        self.added: list = []

    async def execute(self, stmt):
        class _Result:
            @staticmethod
            def scalar_one_or_none():
                return None

        return _Result()

    def add(self, obj):
        obj.id = 42
        self.added.append(obj)

    async def flush(self):
        return None


class _FakeProber:
    """Заглушка SearchUrlProber: возвращает заранее заданный ProbedUrl."""

    def __init__(self, probed=None, error: Exception | None = None):
        self._probed = probed
        self._error = error
        self.calls: list[dict] = []

    async def probe_async(self, base_url, search_query, **kwargs):
        self.calls.append(
            {'base_url': base_url, 'search_query': search_query, **kwargs}
        )
        if self._error is not None:
            raise self._error
        return self._probed


def _probed(param: str = 'q') -> ProbedUrl:
    return ProbedUrl(
        source_name='lenta.ru',
        search_url=f'https://lenta.ru/search?{param}=lenta',
        search_method='GET',
        search_params={param: 'lenta'},
        confidence=1.0,
    )


@pytest.mark.asyncio
async def test_register_without_probe_does_not_touch_network():
    """probe_search выключен по умолчанию: проубер не вызывается."""
    prober = _FakeProber(probed=_probed())
    service = SourceRegistrationService(
        _FakeSession(), redis_client=_FakeRedis(), prober=prober
    )

    result = await service.register(SRC_LENTA_NEWS)

    assert prober.calls == []
    assert result.search_probe is None


@pytest.mark.asyncio
async def test_register_with_probe_caches_source_level_url():
    """probe_search=True: эндпоинт проверен, результат в кэше источника."""
    fake_redis = _FakeRedis()
    prober = _FakeProber(probed=_probed('text'))
    service = SourceRegistrationService(
        _FakeSession(), redis_client=fake_redis, prober=prober
    )

    result = await service.register(SRC_LENTA_NEWS, probe_search=True)

    assert result.search_probe is not None
    assert result.search_probe.search_params == {'text': 'lenta'}
    # Проубер вызван без target_name (конкурента на этом этапе нет).
    assert prober.calls[0]['target_name'] == ''
    # Запись легла в source-level ключ (без хэша поискового запроса).
    assert fake_redis._store.get('bp1:probed_url:lenta.ru') is not None


@pytest.mark.asyncio
async def test_register_probe_failure_does_not_break_registration():
    """Сбой проверки эндпоинта не срывает регистрацию источника."""
    prober = _FakeProber(error=RuntimeError('network down'))
    service = SourceRegistrationService(
        _FakeSession(), redis_client=_FakeRedis(), prober=prober
    )

    result = await service.register(SRC_LENTA_NEWS, probe_search=True)

    assert result.created is True
    assert result.search_probe is None


@pytest.mark.asyncio
async def test_runner_reuses_registration_param_as_hint():
    """AdaptiveRunner берёт имя параметра из записи регистрации."""
    from src.bp1.adaptive.integration.runner import AdaptiveRunner

    fake_redis = _FakeRedis()
    runner = AdaptiveRunner()
    runner._cache.redis = fake_redis
    await runner._cache.set_probed_url('lenta.ru', _probed('text'))

    param = await runner._preferred_param_from_registration('lenta.ru')

    assert param == 'text'


@pytest.mark.asyncio
async def test_runner_param_hint_absent_without_registration():
    """Без записи регистрации подсказки нет (пробинг идёт как раньше)."""
    from src.bp1.adaptive.integration.runner import AdaptiveRunner

    runner = AdaptiveRunner()
    runner._cache.redis = _FakeRedis()

    assert await runner._preferred_param_from_registration('lenta.ru') is None
