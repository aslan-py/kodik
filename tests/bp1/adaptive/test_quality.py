"""Тесты для DataQualityGate."""

from src.bp1.adaptive.quality import DataQualityGate
from src.bp1.adaptive.schemas import QualityGateLevel


def _valid_items() -> list[dict]:
    return [
        {
            'url': 'https://example.com/1',
            'title': 'Новость 1',
            'text': 'Текст новости 1',
            'published_at': '01.01.2026',
            'region': 'Москва',
            'media_name': 'example.com',
        },
        {
            'url': 'https://example.com/2',
            'title': 'Новость 2',
            'text': 'Текст новости 2',
            'published_at': '02.01.2026',
            'region': 'СПб',
            'media_name': 'example.com',
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
        items = [{'url': 'https://example.com/1'}]  # нет title
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
            items, rules=[{'field': 'text', 'min_length': 10}]
        )
        assert report.passed is False


class TestVolumeGate:
    """Уровень 4: VOLUME."""

    def test_volume_drop_warns(self):
        gate = DataQualityGate()
        report = gate.validate_volume(current_count=5, expected_count=10)
        assert report.passed is False
        assert report.warnings

    def test_volume_ok(self):
        gate = DataQualityGate()
        report = gate.validate_volume(current_count=9, expected_count=10)
        assert report.passed is True


class TestConsistencyGate:
    """Уровень 5: CONSISTENCY."""

    def test_duplicates_detected(self):
        gate = DataQualityGate()
        items = [
            {'url': 'https://example.com/1', 'title': 'a'},
            {'url': 'https://example.com/1', 'title': 'b'},
        ]
        report = gate.validate_consistency(items)
        assert report.passed is False
        assert any('duplicate' in e for e in report.errors)


class TestValidateAll:
    """Агрегация всех уровней."""

    def test_all_valid(self):
        gate = DataQualityGate()
        reports = gate.validate_all(_valid_items(), expected_count=2)
        assert gate.is_all_passed(reports) is True
        assert len(reports) == 5

    def test_quarantine_on_failure(self):
        gate = DataQualityGate()
        items = [{'url': 'https://example.com/1'}]  # нет title
        gate.validate_all(items)
        assert len(gate.quarantine_store) > 0
