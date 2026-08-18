"""Тесты для DataQualityGate."""

from src.bp1.adaptive.core.quality import DataQualityGate
from src.bp1.adaptive.schemas import QualityGateLevel

from .constants import (
    DATE_1,
    DATE_2,
    EXAMPLE_SOURCE_NAME,
    NEWS_1,
    NEWS_2,
    NEWS_LINK,
    NEWS_LINK_2,
    QUALITY_ERROR_MISSING_TITLE,
    QUALITY_EXPECTED_COUNT,
    QUALITY_JSON_GLOB,
    QUALITY_MIN_TEXT_LENGTH,
    QUALITY_REPORTS_COUNT,
    QUALITY_VOLUME_CURRENT_LOW,
    QUALITY_VOLUME_CURRENT_OK,
    QUALITY_VOLUME_EXPECTED,
    REGION_1,
    REGION_2,
    TEXT_1,
    TEXT_2,
)


def _valid_items() -> list[dict]:
    return [
        {
            'url': NEWS_LINK,
            'title': NEWS_1,
            'text': TEXT_1,
            'published_at': DATE_1,
            'region': REGION_1,
            'media_name': EXAMPLE_SOURCE_NAME,
        },
        {
            'url': NEWS_LINK_2,
            'title': NEWS_2,
            'text': TEXT_2,
            'published_at': DATE_2,
            'region': REGION_2,
            'media_name': EXAMPLE_SOURCE_NAME,
        },
    ]


class TestSchemaGate:
    """Уровень 1: SCHEMA."""

    def test_valid_items_pass(self):
        gate = DataQualityGate()
        report = gate.validate_schema({'items': _valid_items()})
        assert report.passed is True
        assert report.level == QualityGateLevel.SCHEMA

    def test_missing_required_field_fails(self):
        gate = DataQualityGate()
        items = [{'url': NEWS_LINK}]  # нет title
        report = gate.validate_schema({'items': items})
        assert report.passed is False
        assert any('title' in e for e in report.errors)


class TestTypesGate:
    """Уровень 2: TYPES."""

    def test_wrong_type_fails(self):
        gate = DataQualityGate()
        items = [{'url': 123, 'title': 'x'}]  # url должен быть str
        report = gate.validate_types(items)
        assert report.passed is False
        assert any('url' in e for e in report.errors)


class TestBusinessGate:
    """Уровень 3: BUSINESS."""

    def test_min_length_rule(self):
        gate = DataQualityGate()
        items = [{'url': 'u', 'title': 't', 'text': 'короткий'}]
        report = gate.validate_business_rules(
            items,
            rules=[{'field': 'text', 'min_length': QUALITY_MIN_TEXT_LENGTH}],
        )
        assert report.passed is False


class TestVolumeGate:
    """Уровень 4: VOLUME."""

    def test_volume_drop_warns(self):
        gate = DataQualityGate()
        report = gate.validate_volume(
            current_count=QUALITY_VOLUME_CURRENT_LOW,
            expected_count=QUALITY_VOLUME_EXPECTED,
        )
        assert report.passed is False
        assert report.warnings

    def test_volume_ok(self):
        gate = DataQualityGate()
        report = gate.validate_volume(
            current_count=QUALITY_VOLUME_CURRENT_OK,
            expected_count=QUALITY_VOLUME_EXPECTED,
        )
        assert report.passed is True


class TestConsistencyGate:
    """Уровень 5: CONSISTENCY."""

    def test_duplicates_detected(self):
        gate = DataQualityGate()
        items = [
            {'url': NEWS_LINK, 'title': 'a'},
            {'url': NEWS_LINK, 'title': 'b'},
        ]
        report = gate.validate_consistency(items)
        assert report.passed is False
        assert any('duplicate' in e for e in report.errors)

    def test_duplicate_with_hhtmfrom_noise_normalized(self):
        """URL с мусорным параметром hhtmFrom нормализуется до базового."""
        gate = DataQualityGate()
        items = [
            {'url': '/article/cookie_policy?hhtmFrom=not_found', 'title': 'a'},
            {'url': '/article/cookie_policy', 'title': 'b'},
        ]
        report = gate.validate_consistency(items)
        assert report.passed is False
        assert any('duplicate' in e for e in report.errors)

    def test_url_with_fragment_duplicates(self):
        """URL с якорем и без него — это один и тот же ключ."""
        gate = DataQualityGate()
        items = [
            {'url': 'https://example.com/article#part2', 'title': 'a'},
            {'url': 'https://example.com/article', 'title': 'b'},
        ]
        report = gate.validate_consistency(items)
        assert report.passed is False
        assert any('duplicate' in e for e in report.errors)

    def test_url_trailing_slash_duplicates(self):
        """URL с завершающим слэшем и без него — это один ключ."""
        gate = DataQualityGate()
        items = [
            {'url': 'https://example.com/news/', 'title': 'a'},
            {'url': 'https://example.com/news', 'title': 'b'},
        ]
        report = gate.validate_consistency(items)
        assert report.passed is False

    def test_junk_root_urls_not_flagged_as_duplicates(self):
        """Корневые/пустые URL не участвуют в дедупликации."""
        gate = DataQualityGate()
        items = [
            {'url': '/', 'title': 'a'},
            {'url': '/', 'title': 'b'},
            {'url': '', 'title': 'c'},
            {'url': None, 'title': 'd'},
        ]
        report = gate.validate_consistency(items)
        assert report.passed is True
        assert report.errors == []


class TestRelevanceGate:
    """Уровень 6: RELEVANCE (change verify-search-probe-relevance)."""

    def test_no_target_passes(self):
        """Без competitor/trigger — нечего проверять, проходит всегда."""
        gate = DataQualityGate()
        report = gate.validate_relevance(_valid_items())
        assert report.passed is True
        assert report.level == QualityGateLevel.RELEVANCE

    def test_competitor_mentioned_in_item_passes(self):
        gate = DataQualityGate()
        items = [{'url': NEWS_LINK, 'title': 'Сбербанк открыл филиал'}]
        report = gate.validate_relevance(items, competitor='Сбербанк')
        assert report.passed is True

    def test_competitor_mentioned_in_nested_news_passes(self):
        """Адаптивный сбор несёт реальные материалы в extra.news[] —

        проверяется и там, не только в title/text элемента-обёртки.
        """
        gate = DataQualityGate()
        items = [
            {
                'url': NEWS_LINK,
                'title': 'Страница результатов поиска',
                'extra': {
                    'news': [
                        {
                            'ex_title': 'Сбербанк запустил новый продукт',
                            'ex_url': NEWS_LINK_2,
                        }
                    ]
                },
            }
        ]
        report = gate.validate_relevance(items, competitor='Сбербанк')
        assert report.passed is True

    def test_no_mention_anywhere_fails(self):
        """Регресс-тест на инцидент rbc.ru: ни один материал не упоминает

        конкурента — RELEVANCE проваливается.
        """
        gate = DataQualityGate()
        items = [
            {
                'url': NEWS_LINK,
                'title': 'Страница результатов поиска',
                'extra': {
                    'news': [
                        {'ex_title': 'Совсем другая новость про Яблоко'},
                    ]
                },
            }
        ]
        report = gate.validate_relevance(items, competitor='Сбербанк')
        assert report.passed is False
        assert report.errors

    def test_trigger_mention_is_enough(self):
        """Триггер (тема поиска) тоже засчитывается, не только конкурент."""
        gate = DataQualityGate()
        items = [{'url': NEWS_LINK, 'title': 'Новости про ИИ в банках'}]
        report = gate.validate_relevance(items, trigger='ИИ')
        assert report.passed is True


class TestValidateAll:
    """Агрегация всех уровней."""

    def test_all_valid(self):
        gate = DataQualityGate()
        reports = gate.validate_all(
            _valid_items(), expected_count=QUALITY_EXPECTED_COUNT
        )
        assert gate.is_all_passed(reports) is True
        assert len(reports) == QUALITY_REPORTS_COUNT

    def test_quarantine_on_failure(self):
        gate = DataQualityGate()
        items = [{'url': NEWS_LINK}]  # нет title
        gate.validate_all(items)
        assert len(gate.quarantine_store) > 0


class TestQuarantinePersistence:
    """Персистентность карантина на диске."""

    def test_quarantine_persists_to_disk(self, tmp_path):
        gate = DataQualityGate(quarantine_dir=str(tmp_path))
        gate.quarantine(
            data={'url': NEWS_LINK},
            errors=[QUALITY_ERROR_MISSING_TITLE],
        )
        # Запись сохранена на диск.
        files = list(tmp_path.glob(QUALITY_JSON_GLOB))
        assert len(files) == 1

    def test_quarantine_loaded_from_disk(self, tmp_path):
        gate = DataQualityGate(quarantine_dir=str(tmp_path))
        gate.quarantine(
            data={'url': NEWS_LINK},
            errors=[QUALITY_ERROR_MISSING_TITLE],
        )
        # Новый экземпляр с тем же каталогом загружает записи с диска.
        gate2 = DataQualityGate(quarantine_dir=str(tmp_path))
        assert len(gate2.quarantine_store) == 1
        assert gate2.quarantine_store[0].errors == [QUALITY_ERROR_MISSING_TITLE]

    def test_quarantine_without_dir_not_persisted(self, tmp_path):
        gate = DataQualityGate()
        gate.quarantine(
            data={'url': NEWS_LINK},
            errors=['error'],
        )
        # Без каталога записи остаются только в памяти.
        assert len(gate.quarantine_store) == 1
        assert list(tmp_path.glob(QUALITY_JSON_GLOB)) == []
