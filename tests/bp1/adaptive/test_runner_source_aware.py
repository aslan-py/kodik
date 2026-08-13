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
from src.bp1.adaptive.schemas import SourceClassification, SourceType


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
        'src.bp1.adaptive.integration.runner.get_search_task_config',
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
        'src.bp1.adaptive.integration.runner.RawDataService',
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
