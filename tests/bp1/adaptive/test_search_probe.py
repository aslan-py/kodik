"""Тесты перебора вариантов поиска с проверкой наличия цели в выдаче.

Проверяют ``SearchUrlProber`` и ``score_target_presence`` из
``src.bp1.adaptive.integration.search_probe``:

- case-insensitive поиск цели (регистр, Ё/Е);
- «нет цели в выдаче -> перебор идёт дальше»;
- «есть цель -> winner (первый успешный вариант)»;
- «без цели -> старое поведение (только looks_like_search_results)».
"""

from __future__ import annotations

from urllib.parse import quote_plus

from src.bp1.adaptive.integration.search_probe import (
    _TARGET_CONFIDENT,
    ProbePlan,
    SearchUrlProber,
    _fold,
    build_reformulations,
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
    post: object = None,
) -> SearchUrlProber:
    """Создаёт проубер с фейковым fetch и looks_like_search_results."""

    def fetch(url: str) -> str:
        return responses.get(url, '')

    def looks_like(html: str) -> bool:
        return looks_like and bool(html)

    return SearchUrlProber(
        fetch=fetch,
        looks_like_search_results=looks_like,
        post=post,
    )


# Базовый шаблон источника: ``{q}`` — плейсхолдер ЗНАЧЕНИЯ (как его
# отдаёт SearchUrlTemplateRegistry.build_base_url в рантайме).
BASE = 'https://example.com/search?q={q}'
QUERY = 'ООО АРХИТЕХ'


def _url(param: str, value: str = QUERY) -> str:
    """URL, который построит проубер для пары параметр/значение."""
    return f'https://example.com/search?{param}={quote_plus(value)}'


def test_probe_target_found_wins():
    # Первый параметр даёт выдачу с целью — он и есть winner.
    responses = {_url('q'): '<html><body>ООО АРХИТЕХ</body></html>'}
    prober = _make_prober(responses)
    plan = prober.probe(BASE, QUERY, target_name=QUERY)

    assert len(plan.attempts) == 1
    attempt = plan.attempts[0]
    assert attempt.ok is True
    assert attempt.target_found is True
    assert attempt.target_score == _TARGET_CONFIDENT
    # В параметрах — реальное значение поиска, а не статус попытки.
    assert attempt.params == {'q': QUERY}
    assert attempt.method == 'GET'


def test_probe_target_missing_continues():
    # Первый параметр — выдача без цели, второй — с целью.
    responses = {
        _url('q'): '<html><body>Другая компания</body></html>',
        _url('query'): '<html><body>ООО АРХИТЕХ</body></html>',
    }
    prober = _make_prober(responses)
    plan = prober.probe(BASE, QUERY, target_name=QUERY)

    assert len(plan.attempts) == 2
    assert plan.attempts[0].ok is False
    assert plan.attempts[0].detail == 'empty_results'
    assert plan.attempts[0].target_found is False
    assert plan.attempts[1].ok is True
    assert plan.attempts[1].target_found is True


def test_probe_without_target_uses_looks_like_only():
    # Без target_name — старое поведение: только looks_like_search_results.
    responses = {_url('q'): '<html><body>что-то</body></html>'}
    prober = _make_prober(responses)
    plan = prober.probe(BASE, QUERY)

    assert len(plan.attempts) == 1
    assert plan.attempts[0].ok is True
    assert plan.attempts[0].target_found is False


def test_probe_no_target_anywhere_returns_all_failed():
    # Цели нет ни в одном варианте — все попытки неуспешны.
    responses = {
        _url('q'): '<html><body>Другая компания</body></html>',
        _url('query'): '<html><body>Ещё одна компания</body></html>',
    }
    prober = _make_prober(responses)
    plan = prober.probe(BASE, QUERY, target_name=QUERY)

    assert len(plan.attempts) >= 1
    assert all(a.ok is False for a in plan.attempts)
    assert any(a.detail == 'empty_results' for a in plan.attempts)


def test_probe_prefer_param_first():
    # prefer_param пробуется первым, даже если не в начале цепочки.
    responses = {_url('text'): '<html><body>ООО АРХИТЕХ</body></html>'}
    prober = _make_prober(responses)
    plan = prober.probe(
        BASE,
        QUERY,
        prefer_param='text',
        target_name=QUERY,
    )

    assert len(plan.attempts) == 1
    assert plan.attempts[0].label == 'text'
    assert plan.attempts[0].ok is True


# ---------------------------------------------------------------------------
# Шаг 18: параметр значения, POST-форма, переформулировки
# ---------------------------------------------------------------------------


def test_probe_searches_actual_query_not_param_name():
    """Регресс: раньше в значение подставлялось ИМЯ параметра.

    ``base_url.replace('{q}', param)`` для шаблона ``?text={q}`` давал
    ``?text=q`` — поиск литерала «q» вместо названия компании.
    """
    requested: list[str] = []

    def fetch(url: str) -> str:
        requested.append(url)
        return '<html><body>ООО АРХИТЕХ</body></html>'

    prober = SearchUrlProber(
        fetch=fetch, looks_like_search_results=lambda html: bool(html)
    )
    prober.probe(BASE, QUERY, target_name=QUERY)

    assert requested, 'пробинг не сделал ни одного запроса'
    assert quote_plus(QUERY) in requested[0]
    # Имя параметра не должно оказаться значением.
    assert not requested[0].endswith('=q')


def test_probe_uses_template_param_first():
    """Параметр из шаблона источника пробуется первым.

    ``hh.ru -> /search/vacancy?text={q}``: знание реестра о конкретном
    сайте достовернее общей цепочки параметров.
    """
    base = 'https://hh.ru/search/vacancy?text={q}'
    responses = {
        f'https://hh.ru/search/vacancy?text={quote_plus(QUERY)}': (
            '<html><body>ООО АРХИТЕХ</body></html>'
        )
    }
    prober = _make_prober(responses)
    plan = prober.probe(base, QUERY, target_name=QUERY)

    assert plan.attempts[0].label == 'text'
    assert plan.attempts[0].ok is True


def test_probe_form_skipped_without_post_transport():
    """Без POST-транспорта этап формы честно помечается пропущенным,
    а не имитируется GET-запросом (как было раньше)."""
    prober = _make_prober({})  # все GET-ы вернут '' -> not_search_results
    plan = prober.probe(BASE, QUERY, target_name=QUERY)

    form_attempts = [a for a in plan.attempts if a.kind == 'form']
    assert len(form_attempts) == 1
    assert form_attempts[0].detail == 'no_post_transport'
    assert form_attempts[0].ok is False
    assert form_attempts[0].method == 'POST'


def test_probe_form_post_success():
    """POST-форма выполняется реально и даёт winner с method='POST'."""
    posted: list[tuple[str, dict]] = []

    def post(url: str, params: dict) -> str:
        posted.append((url, params))
        return '<html><body>ООО АРХИТЕХ</body></html>'

    prober = _make_prober({}, post=post)
    plan = prober.probe(BASE, QUERY, target_name=QUERY)

    assert posted == [('https://example.com/search', {'q': QUERY})]
    winner = plan.attempts[-1]
    assert winner.kind == 'form'
    assert winner.ok is True
    assert winner.method == 'POST'
    assert winner.params == {'q': QUERY}


def test_probe_reformulations_simplify_query():
    """Переформулировки реально меняют запрос (раньше повторяли тот же URL).

    Точное название не находится, но упрощённое (без ОПФ) — находится.
    """
    responses = {_url('q', 'АРХИТЕХ'): '<html><body>АРХИТЕХ</body></html>'}
    prober = _make_prober(responses)
    plan = prober.probe(BASE, QUERY, target_name=QUERY)

    winner = plan.attempts[-1]
    assert winner.kind == 'reformulation'
    assert winner.ok is True
    assert winner.params == {'q': 'АРХИТЕХ'}


def test_build_reformulations_variants():
    """Переформулировки: без кавычек, без ОПФ, первое значимое слово."""
    variants = build_reformulations('ООО «АРХИТЕХ ИИ»', limit=5)

    assert 'ООО АРХИТЕХ ИИ' in variants  # без кавычек
    assert 'АРХИТЕХ ИИ' in variants  # без ОПФ
    assert 'АРХИТЕХ' in variants  # первое значимое слово
    # Исходный запрос в переформулировки не попадает.
    assert 'ООО «АРХИТЕХ ИИ»' not in variants
    # Дубликатов нет.
    assert len(variants) == len(set(variants))


def test_build_reformulations_single_word_has_nothing_to_simplify():
    """Одно слово без ОПФ и кавычек — упрощать нечего."""
    assert build_reformulations('Яндекс', limit=5) == []


def test_build_reformulations_respects_limit():
    variants = build_reformulations('ООО «АРХИТЕХ ИИ»', limit=2)
    assert len(variants) == 2


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
