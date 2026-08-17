"""Тесты Source-aware логики AdaptiveRunner (поиск по ИНН vs название).

Проверяют интеграцию ``SearchParamResolver`` и ``missing_inn`` в
``AdaptiveRunner.run_task``:

- гос. источник без ИНН у конкурента -> задача пропускается с
  ``error: not INN`` и записью ``RawItem`` со статусом error;
- гос. источник с ИНН -> поисковый URL строится по ИНН;
- не-гос. источник -> поисковый URL строится по названию конкурента.
"""

from __future__ import annotations

from urllib.parse import unquote

import pytest

from src.bp1.adaptive.integration.runner import AdaptiveRunner
from src.bp1.adaptive.schemas import (
    ProbedUrl,
    SourceClassification,
    SourceType,
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

    async def exists(self, key: str):
        return key in self._store

    async def incr(self, key: str):
        new_value = int(self._store.get(key, 0)) + 1
        self._store[key] = str(new_value)
        return new_value


class _FakeSession:
    """Заглушка AsyncSession: фиксирует вызовы персистентности."""

    def __init__(self):
        self.persisted_errors: list[dict] = []


class _FakeRawDataService:
    """Заглушка RawDataService: фиксирует запись ошибок и persist."""

    def __init__(self, session: _FakeSession):
        self.session = session

    async def persist_error(
        self,
        search_task_id: int,
        error_message: str,
        source_request_url: str | None = None,
    ) -> int:
        self.session.persisted_errors.append(
            {
                'search_task_id': search_task_id,
                'error_message': error_message,
                'source_request_url': source_request_url,
            }
        )
        return 999

    async def persist(
        self,
        search_task_id: int,
        response_data: dict,
        source_request_url: str | None = None,
        html_source_path: str | None = None,
    ) -> dict:
        return {
            'search_task_id': search_task_id,
            'raw_item_id': 1000,
            'status_type': 'new',
            'hash': 'abc',
        }


def _classification(source_type: SourceType) -> SourceClassification:
    return SourceClassification(source_name='src', source_type=source_type)


def _make_runner(monkeypatch, config, classification):
    """Собирает runner с заглушками кэша/классификатора/хранилища."""
    runner = AdaptiveRunner()

    fake_session = _FakeSession()

    async def _fake_get_config(task_id, session):
        return config

    async def _fake_classify(*args, **kwargs):
        return classification

    async def _fake_get_classification(*args, **kwargs):
        return None

    async def _fake_is_blocked(*args, **kwargs):
        return False

    async def _fake_set_classification(*args, **kwargs):
        return None

    # Для тестов всегда используем универсальный адаптивный парсер (None),
    # чтобы не тянуть специализированные RPA-парсеры (fedresurs и др.).
    monkeypatch.setattr(
        runner, '_get_parser_for_source', lambda source_name: None
    )
    monkeypatch.setattr(
        'src.bp1.adaptive.integration.runner.core.get_search_task_config',
        _fake_get_config,
    )
    monkeypatch.setattr(runner._classifier, 'classify', _fake_classify)
    monkeypatch.setattr(
        runner._cache, 'get_classification', _fake_get_classification
    )
    monkeypatch.setattr(
        runner._cache, 'set_classification', _fake_set_classification
    )
    monkeypatch.setattr(runner._cache, 'is_source_blocked', _fake_is_blocked)
    monkeypatch.setattr(
        'src.bp1.adaptive.integration.runner.core.RawDataService',
        lambda session, redis: _FakeRawDataService(session),
    )

    return runner, fake_session


@pytest.mark.asyncio
async def test_run_task_missing_inn_for_gov_source_skips(monkeypatch):
    """Гос. источник без ИНН -> пропуск с error 'not INN'."""
    config = {
        'is_active': True,
        'source_is_active': True,
        'competitor_is_active': True,
        'source': 'https://fedresurs.ru/',
        'competitor': 'ООО Кодик',
        'competitor_inn': None,
        'trigger': None,
    }
    classification = _classification(SourceType.REGISTRY)

    runner, fake_session = _make_runner(monkeypatch, config, classification)
    redis = _FakeRedis()

    result = await runner.run_task(1, fake_session, redis)

    assert result['status'] == 'error'
    assert result['error'] == 'not INN'
    assert fake_session.persisted_errors
    assert fake_session.persisted_errors[0]['error_message'] == 'not INN'


@pytest.mark.asyncio
async def test_run_task_gov_with_inn_uses_inn_in_url(monkeypatch):
    """Гос. источник с ИНН -> URL поиска строится по ИНН."""
    config = {
        'is_active': True,
        'source_is_active': True,
        'competitor_is_active': True,
        'source': 'https://fedresurs.ru/',
        'competitor': 'ООО Кодик',
        'competitor_inn': '9718283930',
        'trigger': None,
    }
    classification = _classification(SourceType.REGISTRY)

    runner, fake_session = _make_runner(monkeypatch, config, classification)
    captured: dict = {}

    async def _fake_parse(url, **kwargs):
        captured['url'] = url

        class _Resp:
            def __init__(self):
                self.items = []

            def model_dump(self):
                return {'items': []}

        return _Resp()

    runner._parser.parse = _fake_parse
    redis = _FakeRedis()

    await runner.run_task(1, fake_session, redis)

    # Пропуска не было (ИНН есть), URL поиска содержит ИНН.
    assert not fake_session.persisted_errors
    assert '9718283930' in captured.get('url', '')


@pytest.mark.asyncio
async def test_run_task_non_gov_uses_competitor_name(monkeypatch):
    """Не-гос. источник -> URL поиска строится по названию конкурента."""
    config = {
        'is_active': True,
        'source_is_active': True,
        'competitor_is_active': True,
        'source': 'https://lenta.ru/',
        'competitor': 'ООО Кодик',
        'competitor_inn': '9718283930',
        'trigger': None,
    }
    classification = _classification(SourceType.NEWS)

    runner, fake_session = _make_runner(monkeypatch, config, classification)
    captured: dict = {}

    async def _fake_parse(url, **kwargs):
        captured['url'] = url

        class _Resp:
            def __init__(self):
                self.items = []

            def model_dump(self):
                return {'items': []}

        return _Resp()

    runner._parser.parse = _fake_parse
    redis = _FakeRedis()

    await runner.run_task(1, fake_session, redis)

    # Для не-гос. источника используется название конкурента, а не ИНН.
    # URL percent-кодируется (quote_plus), поэтому сравниваем через unquote.
    assert 'Кодик' in unquote(captured.get('url', ''))
    assert '9718283930' not in captured.get('url', '')


@pytest.mark.asyncio
async def test_run_task_uses_cached_probed_url(monkeypatch):
    """При закэшированном probed URL парсер получает именно его."""
    config = {
        'is_active': True,
        'source_is_active': True,
        'competitor_is_active': True,
        'source': 'https://lenta.ru/',
        'competitor': 'ООО Кодик',
        'competitor_inn': '9718283930',
        'trigger': None,
    }
    classification = _classification(SourceType.NEWS)
    runner, fake_session = _make_runner(monkeypatch, config, classification)

    # Кладём probed URL в кэш до запуска задачи. Для не-гос. источника
    # (NEWS) поисковый параметр = название конкурента ('ООО Кодик').
    redis = _FakeRedis()
    probed = ProbedUrl(
        source_name='lenta.ru',
        search_url='https://lenta.ru/search/custom?text=cl',
        search_params={'text': 'cl'},
        confidence=1.0,
    )
    # Прокидываем через настоящий кэш в Redis-заглушку по составному ключу
    # (источник + хэш поискового запроса), как это делает runner.
    from src.bp1.adaptive.core.cache import UnifiedCache

    cache = UnifiedCache(redis_client=redis)
    await cache.set_probed_url('lenta.ru', probed, search_param='ООО Кодик')

    captured: dict = {}

    async def _fake_parse(url, **kwargs):
        captured['url'] = url
        captured['probed_url'] = kwargs.get('probed_url')

        class _Resp:
            def __init__(self):
                self.items = []

            def model_dump(self):
                return {'items': []}

        return _Resp()

    runner._parser.parse = _fake_parse

    await runner.run_task(1, fake_session, redis)

    # Используется закэшированный probed URL, а не базовый /search?q=.
    assert captured.get('url') == 'https://lenta.ru/search/custom?text=cl'
    assert captured.get('probed_url') is not None


@pytest.mark.asyncio
async def test_run_task_fallback_when_probe_fails(monkeypatch):
    """При неудачном пробинге используется fallback URL."""
    config = {
        'is_active': True,
        'source_is_active': True,
        'competitor_is_active': True,
        'source': 'https://lenta.ru/',
        'competitor': 'ООО Кодик',
        'competitor_inn': '9718283930',
        'trigger': None,
    }
    classification = _classification(SourceType.NEWS)
    runner, fake_session = _make_runner(monkeypatch, config, classification)
    redis = _FakeRedis()

    captured: dict = {}

    async def _fake_parse(url, **kwargs):
        captured['url'] = url

        class _Resp:
            def __init__(self):
                self.items = []

            def model_dump(self):
                return {'items': []}

        return _Resp()

    runner._parser.parse = _fake_parse

    # Проубер с fetch, который всегда бросает исключение — probe вернёт None,
    # поэтому сработает fallback (без обращения к реальной сети).
    def _failing_fetch(url: str) -> str:
        raise OSError('network down')

    runner.bind_probe_fetch(_failing_fetch)

    await runner.run_task(1, fake_session, redis)

    # Fallback = базовый шаблон lenta.ru -> /search?q=<percent-encoded query>.
    url = captured.get('url', '')
    assert url.startswith('https://lenta.ru/search?q=')
    assert 'Кодик' in unquote(url)


@pytest.mark.asyncio
async def test_run_task_fallback_is_cached_by_query(monkeypatch):
    """Fallback кэшируется по составному ключу (источник + запрос).

    Два разных конкурента на одном источнике получают независимые
    закэшированные fallback URL — для второго конкурента не берётся
    URL, закэшированный для первого.
    """
    config_a = {
        'is_active': True,
        'source_is_active': True,
        'competitor_is_active': True,
        'source': 'https://lenta.ru/',
        'competitor': 'ООО Кодик',
        'competitor_inn': None,
        'trigger': None,
    }
    classification = _classification(SourceType.NEWS)
    redis = _FakeRedis()

    def _failing_fetch(url: str) -> str:
        raise OSError('network down')

    async def _fake_parse(url, **kwargs):
        class _Resp:
            def __init__(self):
                self.items = []

            def model_dump(self):
                return {'items': []}

        return _Resp()

    # Задача по конкуренту A.
    runner_a, _ = _make_runner(monkeypatch, config_a, classification)
    runner_a._parser.parse = _fake_parse
    runner_a.bind_probe_fetch(_failing_fetch)
    await runner_a.run_task(1, _FakeSession(), redis)

    # Кэш для A записан; пробинг больше не должен выполняться для A.
    config_b = dict(config_a, competitor='ООО Бета')
    runner_b, _ = _make_runner(monkeypatch, config_b, classification)
    runner_b._parser.parse = _fake_parse

    called: dict = {}

    def _counting_fetch(url: str) -> str:
        called['n'] = called.get('n', 0) + 1
        raise OSError('network down')

    runner_b.bind_probe_fetch(_counting_fetch)
    await runner_b.run_task(2, _FakeSession(), redis)

    # Для конкурента B пробинг был выполнен заново (свой ключ в кэше),
    # потому что у A и B разные search_param и, как следствие, разные ключи.
    assert called.get('n', 0) >= 1


# ---------------------------------------------------------------------------
# _get_or_probe_url: снимок карточек для сравнения между конкурентами
# ---------------------------------------------------------------------------


class _FakeProber:
    """Фейковый SearchUrlProber.probe_async: фиксирует kwargs, отдаёт canned."""

    def __init__(self, result: ProbedUrl):
        self._result = result
        self.calls: list[dict] = []

    async def probe_async(self, **kwargs):
        self.calls.append(kwargs)
        return self._result


@pytest.mark.asyncio
async def test_get_or_probe_url_passes_known_other_urls_from_sample_cache():
    """Снимок карточек предыдущего конкурента на источнике передаётся

    в SearchUrlProber.probe_async как known_other_result_urls.
    """
    runner = AdaptiveRunner(use_probing=True)
    redis = _FakeRedis()
    runner._bind_redis(redis)
    await runner._cache.set_probed_sample_urls(
        'lenta.ru',
        ['https://lenta.ru/news/1', 'https://lenta.ru/news/2'],
    )

    prober = _FakeProber(
        ProbedUrl(
            source_name='lenta.ru',
            search_url='https://lenta.ru/search?text=NewCo',
        )
    )
    runner._prober = prober

    url, _ = await runner._get_or_probe_url('lenta.ru', 'NewCo', 'NewCo', redis)

    assert url == 'https://lenta.ru/search?text=NewCo'
    assert prober.calls[0]['known_other_result_urls'] == {
        'https://lenta.ru/news/1',
        'https://lenta.ru/news/2',
    }


@pytest.mark.asyncio
async def test_get_or_probe_url_no_known_other_urls_on_cold_start():
    """Без сохранённого снимка (первый конкурент на источнике) —

    known_other_result_urls не передаётся, пробинг не падает.
    """
    runner = AdaptiveRunner(use_probing=True)
    redis = _FakeRedis()
    runner._bind_redis(redis)

    prober = _FakeProber(
        ProbedUrl(
            source_name='rbc.ru', search_url='https://rbc.ru/search?query=X'
        )
    )
    runner._prober = prober

    url, _ = await runner._get_or_probe_url('rbc.ru', 'X', 'X', redis)

    assert url == 'https://rbc.ru/search?query=X'
    assert prober.calls[0]['known_other_result_urls'] is None


@pytest.mark.asyncio
async def test_get_or_probe_url_saves_sample_urls_after_success():
    """Успешный пробинг сохраняет снимок карточек для будущих конкурентов

    на том же источнике.
    """
    runner = AdaptiveRunner(use_probing=True)
    redis = _FakeRedis()
    runner._bind_redis(redis)

    prober = _FakeProber(
        ProbedUrl(
            source_name='lenta.ru',
            search_url='https://lenta.ru/search?text=Comp',
            sample_item_urls=['https://lenta.ru/a', 'https://lenta.ru/b'],
        )
    )
    runner._prober = prober

    await runner._get_or_probe_url('lenta.ru', 'Comp', 'Comp', redis)

    saved = await runner._cache.get_probed_sample_urls('lenta.ru')
    assert set(saved) == {'https://lenta.ru/a', 'https://lenta.ru/b'}
