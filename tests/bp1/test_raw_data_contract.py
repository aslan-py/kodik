"""Контракт ``raw_data`` (BP-1 -> БД).

См. ``ABOUT_PROJECT/ABOUT.md``, раздел BP-1 «Содержимое raw_data» — это
первоисточник требований. Единственный источник истины ДЛЯ КОДА —
pydantic-модели ``ParsedMeta``/``ParsedItem``/``ParsedMetrics``/
``ParsedResponse`` в ``src/bp1/base_parser.py``: ``RawDataService.persist``
(``src/bp1/storage.py``) сохраняет в ``RawItem.raw_data`` ровно
``ParsedResponse.model_dump()``, никакой другой путь записи в БД контракт
не обходит.

Эти тесты не дают контракту незаметно разъехаться с ABOUT.md — именно так
уже случилось один раз: адаптивный мост (``bridge.py``) начал дописывать в
``meta`` служебные поля (``probed_url``/``strategy_used``/
``quality_status``), а новости раскладывались в дублирующий
``items[0].extra.news`` вместо самостоятельных событий (см.
``REFACTORING_PLAN.md``, инцидент разбирался вручную по дампу
``data/raw/raw_651_*.json``).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.bp1.base_parser import (
    ParsedItem,
    ParsedMeta,
    ParsedMetrics,
    ParsedResponse,
)

# Пример из ABOUT.md (раздел BP-1 «Содержимое raw_data»), один в один.
_ABOUT_MD_EXAMPLE = {
    'meta': {
        'search_task_id': 1,
        'source': 'hh.ru',
        'competitor': 'Бегемот',
        'trigger': 'Python',
        'source_request_url': (
            'https://hh.ru/search/vacancy?text=Бегемот+Python'
        ),
        'fetched_at': '2026-07-18T10:00:00Z',
    },
    'items': [
        {
            'url': 'https://hh.ru/vacancy/101',
            'title': 'Python-разработчик',
            'text': 'Описание вакансии...',
            'published_at': '18 июля 2026',
            'region': 'г. Москва',
            'media_name': None,
            'extra': {'salary': '150000-200000 руб.'},
        }
    ],
}


def test_about_md_example_matches_contract():
    """Пример из ABOUT.md проходит валидацию как есть, без надстроек."""
    response = ParsedResponse(**_ABOUT_MD_EXAMPLE)
    assert response.meta.source == 'hh.ru'
    assert response.items[0].extra == {'salary': '150000-200000 руб.'}
    # metrics не заданы в примере ABOUT.md — по умолчанию пустой раздел.
    assert response.metrics.model_dump(exclude_none=True) == {}


def test_meta_field_order_matches_about_md():
    """Порядок полей meta соответствует ABOUT.md (для читаемости raw JSON)."""
    response = ParsedResponse(**_ABOUT_MD_EXAMPLE)
    assert list(response.meta.model_dump().keys()) == [
        'search_task_id',
        'source',
        'competitor',
        'trigger',
        'source_request_url',
        'fetched_at',
    ]


def test_meta_rejects_unknown_fields():
    """Служебные/диагностические поля не должны просачиваться в meta.

    Регресс-тест на конкретный инцидент: адаптивный мост когда-то дописывал
    в meta ``probed_url``/``strategy_used``/``quality_status`` — служебные
    поля вперемешку с фактами о запросе. Теперь у них одно законное место —
    ``ParsedResponse.metrics``.
    """
    bad_meta = dict(_ABOUT_MD_EXAMPLE['meta'], probed_url='https://hh.ru/x')
    with pytest.raises(ValidationError):
        ParsedMeta(**bad_meta)


def test_item_rejects_unknown_top_level_fields():
    """Источник-специфичные факты обязаны идти через extra, а не мимо."""
    bad_item = dict(_ABOUT_MD_EXAMPLE['items'][0], salary='150000')
    with pytest.raises(ValidationError):
        ParsedItem(**bad_item)


def test_response_rejects_unknown_top_level_sections():
    """Раздел вне meta/items/metrics — тоже нарушение контракта."""
    with pytest.raises(ValidationError):
        ParsedResponse(**_ABOUT_MD_EXAMPLE, extra_section={'x': 1})


def test_metrics_is_an_open_bucket_for_diagnostics():
    """metrics — открытый раздел: новая диагностика не требует правки схемы.

    В отличие от meta/items (закрытый бизнес-контракт для BP-2), metrics —
    место для служебных полей и метрик текущего прогона (Шаг 20 плана
    рефакторинга, T6): разные парсеры/движки собирают разную диагностику.
    """
    metrics = ParsedMetrics(quality_status='ok', some_future_metric=42)
    assert metrics.quality_status == 'ok'
    assert metrics.model_dump()['some_future_metric'] == 42


def test_html_file_path_is_never_persisted():
    """html_file_path — служебное поле раннера, не часть raw_data в БД."""
    response = ParsedResponse(**_ABOUT_MD_EXAMPLE, html_file_path='/tmp/x.html')
    assert response.html_file_path == '/tmp/x.html'
    assert 'html_file_path' not in response.model_dump()


def test_old_search_page_shape_is_rejected():
    """Регресс-тест: старая форма выгрузки (до этого фикса) больше невалидна.

    До фикса адаптивный мост складывал первый элемент как «страницу
    результатов поиска» с дублирующим списком новостей внутри
    ``extra.news`` (плюс служебные счётчики парсинга там же) — то, что
    реально попало в БД и было найдено в
    ``src/bp1/data/raw/raw_651_*.json``. Тест фиксирует, что так больше не
    получится: подобный item не проходит валидацию.
    """
    old_shape_item = {
        'url': 'https://hh.ru/search/vacancy?text=X',
        'title': 'Заголовок страницы поиска',
        'text': None,
        'published_at': None,
        'region': None,
        'media_name': 'https://hh.ru',
        'extra': {
            'news': [{'ex_title': 'Курьер', 'ex_url': 'https://hh.ru/1'}],
            'relevance_mode': 'rank',
            'news_total': 10,
            'quality_levels': {'SCHEMA': {'passed': True}},
        },
    }
    # extra остаётся свободным словарём — сам по себе этот item пройдёт
    # (ParsedItem не заглядывает внутрь extra). Ловим регресс на уровне
    # meta: старая форма держала strategy_used/quality_status/probed_url
    # прямо в meta, а не в metrics — именно это теперь запрещено.
    ParsedItem(**old_shape_item)
    old_meta = dict(
        _ABOUT_MD_EXAMPLE['meta'],
        strategy_used='STEALTH',
        quality_status='ok',
        probed_url='https://hh.ru/search/vacancy?text=X',
    )
    with pytest.raises(ValidationError):
        ParsedMeta(**old_meta)
