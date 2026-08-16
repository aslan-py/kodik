"""Тесты перебора вариантов поиска с проверкой наличия цели в выдаче.

Проверяют ``SearchUrlProber`` и ``score_target_presence`` из
``src.bp1.adaptive.integration.search_probe``:

- case-insensitive поиск цели (регистр, Ё/Е);
- «нет цели в выдаче -> перебор идёт дальше»;
- «есть цель -> winner (первый успешный вариант)»;
- «без цели -> старое поведение (только looks_like_search_results)».
"""

from __future__ import annotations

from src.bp1.adaptive.integration.search_probe import (
    _TARGET_CONFIDENT,
    ProbePlan,
    SearchUrlProber,
    _fold,
    score_target_presence,
)

# ---------------------------------------------------------------------------
# score_target_presence
# ---------------------------------------------------------------------------


def test_fold_lowercases_and_replaces_yo():
    assert _fold('ООО АРХИТЕХ') == 'ооо архитех'
    assert _fold('Берёза') == 'береза'
    assert _fold('Ёлка') == 'елка'


def test_score_target_presence_case_insensitive_hit():
    # Строка поиска в HTML в другом регистре — цель найдена.
    html = '<html><body>ООО Архитех — вакансии</body></html>'
    assert score_target_presence(html, 'ООО АРХИТЕХ') == _TARGET_CONFIDENT


def test_score_target_presence_yo_equivalence():
    # Сайт пишет «е» вместо «ё» — цель найдена.
    html = '<html><body>Береза Строй</body></html>'
    assert score_target_presence(html, 'Берёза Строй') == _TARGET_CONFIDENT


def test_score_target_presence_miss():
    html = '<html><body>Другая компания</body></html>'
    assert score_target_presence(html, 'ООО АРХИТЕХ') == 0


def test_score_target_presence_empty_query():
    # Пустой search_query — цель не задана, всегда 0.
    html = '<html><body>ООО АРХИТЕХ</body></html>'
    assert score_target_presence(html, '') == 0


def test_score_target_presence_no_normalization():
    # Без нормализации ОПФ/кавычек/тире: «ООО АРХИТЕХ» не равно «Архитех».
    html = '<html><body>Архитех</body></html>'
    assert score_target_presence(html, 'ООО АРХИТЕХ') == 0


# ---------------------------------------------------------------------------
# SearchUrlProber
# ---------------------------------------------------------------------------


def _make_prober(
    responses: dict[str, str],
    looks_like: bool = True,
) -> SearchUrlProber:
    """Создаёт проубер с фейковым fetch и looks_like_search_results."""

    def fetch(url: str) -> str:
        return responses.get(url, '')

    def looks_like(html: str) -> bool:
        return looks_like and bool(html)

    return SearchUrlProber(fetch=fetch, looks_like_search_results=looks_like)


def test_probe_target_found_wins():
    # Первый параметр даёт выдачу с целью — он и есть winner.
    base = 'https://example.com/search?{q}='
    responses = {
        base.replace('{q}', 'q'): '<html><body>ООО АРХИТЕХ</body></html>',
    }
    prober = _make_prober(responses)
    plan = prober.probe(base, 'ООО АРХИТЕХ', target_name='ООО АРХИТЕХ')

    assert len(plan.attempts) == 1
    attempt = plan.attempts[0]
    assert attempt.ok is True
    assert attempt.target_found is True
    assert attempt.target_score == _TARGET_CONFIDENT


def test_probe_target_missing_continues():
    # Первый параметр — выдача без цели, второй — с целью.
    base = 'https://example.com/search?{q}='
    responses = {
        base.replace('{q}', 'q'): '<html><body>Другая компания</body></html>',
        base.replace('{q}', 'query'): ('<html><body>ООО АРХИТЕХ</body></html>'),
    }
    prober = _make_prober(responses)
    plan = prober.probe(base, 'ООО АРХИТЕХ', target_name='ООО АРХИТЕХ')

    assert len(plan.attempts) == 2
    assert plan.attempts[0].ok is False
    assert plan.attempts[0].detail == 'empty_results'
    assert plan.attempts[0].target_found is False
    assert plan.attempts[1].ok is True
    assert plan.attempts[1].target_found is True


def test_probe_without_target_uses_looks_like_only():
    # Без target_name — старое поведение: только looks_like_search_results.
    base = 'https://example.com/search?{q}='
    responses = {
        base.replace('{q}', 'q'): '<html><body>что-то</body></html>',
    }
    prober = _make_prober(responses)
    plan = prober.probe(base, 'ООО АРХИТЕХ')

    assert len(plan.attempts) == 1
    assert plan.attempts[0].ok is True
    assert plan.attempts[0].target_found is False


def test_probe_no_target_anywhere_returns_all_failed():
    # Цели нет ни в одном варианте — все попытки неуспешны.
    base = 'https://example.com/search?{q}='
    responses = {
        base.replace('{q}', 'q'): '<html><body>Другая компания</body></html>',
        base.replace('{q}', 'query'): (
            '<html><body>Ещё одна компания</body></html>'
        ),
    }
    prober = _make_prober(responses)
    plan = prober.probe(base, 'ООО АРХИТЕХ', target_name='ООО АРХИТЕХ')

    assert len(plan.attempts) >= 1
    assert all(a.ok is False for a in plan.attempts)
    assert any(a.detail == 'empty_results' for a in plan.attempts)


def test_probe_prefer_param_first():
    # prefer_param пробуется первым, даже если не в начале цепочки.
    base = 'https://example.com/search?{q}='
    responses = {
        base.replace('{q}', 'text'): '<html><body>ООО АРХИТЕХ</body></html>',
    }
    prober = _make_prober(responses)
    plan = prober.probe(
        base,
        'ООО АРХИТЕХ',
        prefer_param='text',
        target_name='ООО АРХИТЕХ',
    )

    assert len(plan.attempts) == 1
    assert plan.attempts[0].label == 'text'
    assert plan.attempts[0].ok is True


def test_probe_plan_to_extra():
    plan = ProbePlan()
    plan.add(
        'param',
        'q',
        'https://example.com/search?q=x',
        ok=True,
        detail='ok',
        target_found=True,
        target_score=_TARGET_CONFIDENT,
    )
    extra = plan.to_extra()
    assert 'probe_attempts' in extra
    assert extra['probe_attempts'][0]['kind'] == 'param'
    assert extra['probe_attempts'][0]['target_found'] is True
    assert extra['probe_attempts'][0]['target_score'] == _TARGET_CONFIDENT
