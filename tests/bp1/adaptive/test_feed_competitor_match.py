"""Тесты разметки материалов фида по совпадению с конкурентом
(competitor_match.py, design.md D6 — без LLM)."""

from src.bp1.adaptive.processing.feed.competitor_match import (
    annotate_materials,
    matches_competitor,
    normalize_name,
)


class TestNormalizeName:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_name('ООО «Бегемот»') == normalize_name('ооо бегемот')

    def test_collapses_whitespace(self):
        assert normalize_name('А    Б') == 'а б'

    def test_empty_string(self):
        assert normalize_name('') == ''


class TestMatchesCompetitor:
    def test_exact_match_found_in_title(self):
        material = {'ex_title': 'Бегемот выиграл тендер', 'ex_text': ''}
        assert matches_competitor(material, 'Бегемот') is True

    def test_match_found_in_text(self):
        material = {
            'ex_title': 'Новости региона',
            'ex_text': 'Компания Бегемот объявила о расширении',
        }
        assert matches_competitor(material, 'Бегемот') is True

    def test_case_and_punctuation_insensitive(self):
        material = {'ex_title': 'компания «БЕГЕМОТ» подала иск', 'ex_text': ''}
        assert matches_competitor(material, 'бегемот') is True

    def test_no_match(self):
        material = {'ex_title': 'Новость ни о чём', 'ex_text': 'текст'}
        assert matches_competitor(material, 'Бегемот') is False

    def test_empty_competitor_never_matches(self):
        material = {'ex_title': 'Бегемот', 'ex_text': ''}
        assert matches_competitor(material, '') is False


class TestAnnotateMaterials:
    def test_matched_material_gets_relevance_one(self):
        materials = [{'ex_title': 'Бегемот', 'ex_text': ''}]

        annotated = annotate_materials(materials, 'Бегемот')

        assert annotated[0]['relevance'] == 1.0

    def test_unmatched_material_kept_with_relevance_zero(self):
        materials = [{'ex_title': 'Другая новость', 'ex_text': ''}]

        annotated = annotate_materials(materials, 'Бегемот')

        assert len(annotated) == 1
        assert annotated[0]['relevance'] == 0.0

    def test_does_not_mutate_input(self):
        materials = [{'ex_title': 'Бегемот', 'ex_text': ''}]

        annotate_materials(materials, 'Бегемот')

        assert 'relevance' not in materials[0]

    def test_mixed_batch_keeps_all_items(self):
        materials = [
            {'ex_title': 'Бегемот выиграл суд', 'ex_text': ''},
            {'ex_title': 'Другая компания', 'ex_text': ''},
        ]

        annotated = annotate_materials(materials, 'Бегемот')

        assert len(annotated) == 2
        assert annotated[0]['relevance'] == 1.0
        assert annotated[1]['relevance'] == 0.0
