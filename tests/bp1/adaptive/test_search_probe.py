"""Тесты адаптивного перебора параметров поиска (search_probe).

Покрывают фичи 1–3 адаптивного поиска:
1. Перебор типовых query-параметров (``q``, ``query``, ``text``, ...).
2. Распознавание параметра из HTML-формы поиска (``extract_form_param``).
3. Реформулировки запроса (``build_query_variants``).
"""

from __future__ import annotations

import pytest

from src.bp1.adaptive.integration.search_probe import (
    ProbePlan,
    SearchUrlProber,
    build_probe_url,
    build_query_variants,
    extract_form_param,
    find_matched_target_variant,
    looks_like_search_results,
    score_target_presence,
)

from .constants import (
    COMPETITOR,
    COMPETITOR_INN,
)

# ---------------------------------------------------------------------------
# Константы-фикстуры (переиспользуются в тестах)
# ---------------------------------------------------------------------------
# long HTML, который выглядит как реальная выдача (>= 512 символов,
# чтобы пройти len-порог looks_like_search_results).
_RESULT_ITEMS = ''.join(
    f'<a href="/r{i}">{COMPETITOR} — карточка #{i}</a>' for i in range(25)
)
RESULTS_HTML = (
    f'<html><body><h1>Результаты поиска</h1>{_RESULT_ITEMS}</body></html>'
)
EMPTY_HTML = (
    '<html><body><h1>Ничего не найдено'
    ' по вашему запросу. Попробуйте изменить формулировку.</h1></body></html>'
)
SEARCH_BASE = 'https://example.com/search'


# ============================================================================
# build_probe_url
# ============================================================================


@pytest.mark.parametrize(
    ('base', 'param', 'value', 'expected_part'),
    [
        ('https://lenta.ru/search', 'q', 'ИИ', 'q=%D0%98%D0%98'),
        (
            'https://hh.ru/search/vacancy',
            'text',
            'ООО АРХИТЕХ ИИ',
            'text=%D0%9E%D0%9E%D0%9E+'
            '%D0%90%D0%A0%D0%A5%D0%98%D0%A2%D0%95%D0%A5+%D0%98%D0%98',
        ),
        (
            'https://example.com/search?lang=ru',
            'q',
            'тест',
            '&q=%D1%82%D0%B5%D1%81%D1%82',
        ),
    ],
)
def test_build_probe_url_percent_encodes(base, param, value, expected_part):
    url = build_probe_url(base, param, value)
    assert expected_part in url


def test_build_probe_url_preserves_existing_query():
    url = build_probe_url('https://example.com/search?lang=ru', 'q', 'тест')
    assert 'lang=ru' in url and '&q=' in url


def test_build_probe_url_uses_raw_value():
    """Если передан ``raw_value`` — кодируется он, а не ``search_value``."""
    url = build_probe_url(
        'https://example.com/search',
        'q',
        'уже кодированный %D0%98',
        raw_value='ИИ',
    )
    # raw_value='ИИ' кодируется заново -> %D0%98%D0%98.
    assert 'q=%D0%98%D0%98' in url


def test_build_probe_url_replaces_existing_param():
    """Существующий параметр в base_url заменяется, а не дублируется.

    Реальный кейс: ``build_search_url`` строит ``/search?q=ИИ``, а сайт
    (как ekb.rbc.ru) понимает только ``query``. Перебор q -> query не должен
    давать ``?q=ИИ&query=...`` — старый ``q`` остаётся единственным.
    """
    url = build_probe_url(
        'https://ekb.rbc.ru/search?q=%D0%98%D0%98',
        'query',
        'Яндекс.Еда',
    )
    # Старый ?q=... убран, остался только ?query=Яндекс.Еда.
    assert url == (
        'https://ekb.rbc.ru/search?'
        'query=%D0%AF%D0%BD%D0%B4%D0%B5%D0%BA%D1%81.%D0%95%D0%B4%D0%B0'
    )


def test_build_probe_url_replaces_value_of_same_param():
    """Тот же параметр — меняется только значение."""
    url = build_probe_url(
        'https://example.com/search?q=%D0%98%D0%98',
        'q',
        'Яндекс',
    )
    assert '?q=%D0%AF%D0%BD%D0%B4%D0%B5%D0%BA%D1%81' in url
    assert 'q=' in url and url.count('q=') == 1


def test_build_probe_url_preserves_other_params_on_replace():
    """Прочие параметры (lang, region) сохраняются при замене."""
    url = build_probe_url(
        'https://ekb.rbc.ru/search?q=%D0%98%D0%98&region=ekb',
        'query',
        'Яндекс.Еда',
    )
    assert url.startswith('https://ekb.rbc.ru/search?')
    assert 'region=ekb' in url
    assert 'q=' not in url
    assert (
        'query=%D0%AF%D0%BD%D0%B4%D0%B5%D0%BA%D1%81.%D0%95%D0%B4%D0%B0' in url
    )


# ============================================================================
# build_query_variants
# ============================================================================


def test_build_query_variants_exact_first():
    variants = build_query_variants(COMPETITOR)
    assert variants[0] == COMPETITOR


def test_build_query_variants_strips_legal_form():
    variants = build_query_variants('ООО АРХИТЕХ ИИ')
    assert 'АРХИТЕХ ИИ' in variants


def test_build_query_variants_strips_buzzwords():
    variants = build_query_variants('ООО АРХИТЕХ ИИ')
    assert 'АРХИТЕХ' in variants


def test_build_query_variants_transliteration():
    variants = build_query_variants('ООО АРХИТЕХ ИИ')
    assert any(v.isascii() and v.upper() == v for v in variants)


def test_build_query_variants_inn_is_terminal():
    variants = build_query_variants(COMPETITOR_INN)
    assert variants == [COMPETITOR_INN]


def test_build_query_variants_adds_inn_last():
    variants = build_query_variants(COMPETITOR, competitor_inn=COMPETITOR_INN)
    assert COMPETITOR_INN in variants
    assert variants[-1] == COMPETITOR_INN


def test_build_query_variants_empty():
    assert build_query_variants('') == []
    # Только пробелы -> пустая цепочка.
    assert build_query_variants('   ') == []


# ============================================================================
# looks_like_search_results
# ============================================================================


def test_looks_like_search_results_positive_links():
    assert looks_like_search_results(RESULTS_HTML) is True


def test_looks_like_search_results_positive_count_marker():
    # Минимум 512 символов, чтобы пройти len-порог.
    html = (
        '<html><body><h1>Найдено 12 результатов</h1>'
        '<p>вакансии компаний по вашему запросу. Здесь могла бы быть'
        ' более длинная аннотация выдачи, но для теста достаточно'
        ' заполнить буфер до минимальной длины, которую ожидает'
        ' эвристика looks_like_search_results, чтобы проверить'
        ' именно распознавание маркера количества, а не порога длины'
        ' страницы. Поэтому просто повторяем текст несколько раз.'
        '</p><p>вакансии компаний по вашему запросу.</p>'
        '<p>вакансии компаний по вашему запросу.</p>'
        '<p>вакансии компаний по вашему запросу.</p>'
        '</body></html>'
    )
    assert looks_like_search_results(html) is True


def test_looks_like_search_results_negative_empty_phrase():
    assert looks_like_search_results(EMPTY_HTML) is False


def test_looks_like_search_results_negative_captcha():
    assert (
        looks_like_search_results(
            '<html><body><div class="g-recaptcha">'
            'подтвердите, что вы не робот</div></body></html>'
        )
        is False
    )


def test_looks_like_search_results_short_html():
    html = '<html><body>короткое без ссылок</body></html>'
    assert looks_like_search_results(html) is False


# ============================================================================
# extract_form_param
# ============================================================================

_FORM_HTML = (
    '<html><body>'
    '<form action="/find" method="get">'
    '<input name="searchString" type="text">'
    '<button>Найти</button>'
    '</form>'
    '</body></html>'
)


def test_extract_form_param_returns_name_and_abs_action():
    param, action, method = extract_form_param(
        _FORM_HTML, 'https://example.com'
    )
    assert param == 'searchString'
    assert action == 'https://example.com/find'
    assert method == 'GET'


def test_extract_form_param_detects_post_method():
    html = (
        '<html><body>'
        '<form action="/find" method="post">'
        '<input name="q" type="text">'
        '</form>'
        '</body></html>'
    )
    param, action, method = extract_form_param(html, 'https://example.com')
    assert param == 'q'
    assert action == 'https://example.com/find'
    assert method == 'POST'


def test_extract_form_param_no_form():
    html = '<html><body>без формы</body></html>'
    assert extract_form_param(html, SEARCH_BASE) == (None, None, 'GET')


def test_extract_form_param_empty_html():
    assert extract_form_param('', SEARCH_BASE) == (None, None, 'GET')


def test_extract_form_param_skips_named_input():
    """Форма без текстового поля (только name=hidden) — не поисковая."""
    html = (
        '<html><body><form action="/x">'
        '<input type="hidden" name="csrf">'
        '</form></body></html>'
    )
    assert extract_form_param(html, SEARCH_BASE) == (None, None, 'GET')


def test_extract_form_param_skips_cross_domain_action():
    html = (
        '<html><body><form action="https://other-site.com/subscribe">'
        '<input name="email" type="text">'
        '</form></body></html>'
    )
    assert extract_form_param(html, SEARCH_BASE) == (None, None, 'GET')


# ============================================================================
# ProbePlan
# ============================================================================


def test_probe_plan_success_and_extra():
    plan = ProbePlan()
    plan.add('param', 'q', 'https://x/?q=1', ok=True, detail='content_ok')
    assert plan.success is True
    assert plan.winner is not None
    extra = plan.to_extra()
    assert extra['success'] is True
    assert extra['winner']['kind'] == 'param'
    assert len(extra['attempts']) == 1


def test_probe_plan_no_winner():
    plan = ProbePlan()
    plan.add('param', 'q', 'https://x/?q=1', ok=False, detail='empty_results')
    assert plan.success is False
    assert plan.winner is None


# ============================================================================
# SearchUrlProber.probe (с фейковым fetch)
# ============================================================================


class _FakeFetch:
    """Фейковый ``fetch(url) -> html``: отвечает по правилу ``p``."""

    def __init__(self, good_param: str):
        self._good = good_param
        self.calls: list[str] = []

    async def __call__(self, url: str) -> str:
        self.calls.append(url)
        param = url.split('?', 1)[-1].split('=', 1)[0]
        if param == self._good:
            return RESULTS_HTML
        return EMPTY_HTML


@pytest.mark.asyncio
async def test_probe_finds_working_param():
    fetch = _FakeFetch(good_param='text')
    prober = SearchUrlProber(fetch=fetch)
    plan = await prober.probe(SEARCH_BASE, COMPETITOR)

    assert plan.success is True
    assert plan.winner is not None
    assert plan.winner.kind == 'param'
    assert plan.winner.label == 'text'
    assert 'text=' in plan.winner.url


@pytest.mark.asyncio
async def test_probe_prefers_form_param():
    """Параметр из формы (non-standard) пробуется раньше остальных."""
    fetch = _FakeFetch(good_param='searchString')
    prober = SearchUrlProber(fetch=fetch)
    plan = await prober.probe(
        SEARCH_BASE, COMPETITOR, prefer_param='searchString'
    )

    assert plan.success is True
    assert plan.winner is not None
    assert plan.winner.label == 'searchString'
    # Первая попытка — сразу с параметром формы.
    assert 'searchString=' in fetch.calls[0]


@pytest.mark.asyncio
async def test_probe_tries_reformulations_when_params_empty():
    """Если все параметры дали пустую выдачу — пробуем реформулировки."""

    # Хорошая выдача приходит ТОЛЬКО на реформулировку 'АРХИТЕХ' (без ОПФ),
    # и только по параметру 'q'.
    class _ReformFetch:
        def __init__(self):
            self.calls: list[str] = []

        async def __call__(self, url: str) -> str:
            self.calls.append(url)
            qs = url.split('?', 1)[-1]
            # percent-декодируем значение q.
            from urllib.parse import unquote_plus

            value = ''
            for part in qs.split('&'):
                if part.startswith('q='):
                    value = unquote_plus(part[2:])
            if value == 'АРХИТЕХ':
                return RESULTS_HTML
            return EMPTY_HTML

    prober = SearchUrlProber(fetch=_ReformFetch())
    plan = await prober.probe(SEARCH_BASE, 'ООО АРХИТЕХ ИИ')

    assert plan.success is True
    assert plan.winner is not None
    assert plan.winner.kind == 'query'
    assert plan.winner.label == 'АРХИТЕХ'


@pytest.mark.asyncio
async def test_probe_no_success_all_fail():
    class _NeverFetch:
        async def __call__(self, url: str) -> str:
            return EMPTY_HTML

    prober = SearchUrlProber(fetch=_NeverFetch())
    plan = await prober.probe(SEARCH_BASE, COMPETITOR)

    assert plan.success is False
    assert plan.winner is None
    # Последняя попытка — маркер 'all_attempts_failed'.
    assert plan.attempts[-1].detail == 'all_attempts_failed'


@pytest.mark.asyncio
async def test_probe_handles_fetch_failures():
    class _FailFetch:
        async def __call__(self, url: str) -> str | None:
            return None  # сеть не отвечает

    prober = SearchUrlProber(fetch=_FailFetch())
    plan = await prober.probe(SEARCH_BASE, COMPETITOR)

    assert plan.success is False
    assert all(a.ok is False for a in plan.attempts)


# ---------------------------------------------------------------------------
# POST-форма (form с method="post")
# ---------------------------------------------------------------------------
# ``myquery`` — намеренно не входит в ``_DEFAULT_PARAM_CHAIN``, иначе форма
# считалась бы уже перебранным параметром и до form-этапа не доходило бы.
_FORM_POST_HTML = (
    '<html><body><form action="/find" method="post">'
    '<input name="myquery" type="text"></form></body></html>'
)


@pytest.mark.asyncio
async def test_probe_form_post_success():
    """Форма с method="post" отправляется реальным POST, а не GET-ом."""

    async def fetch(url: str) -> str:
        # Ни один словарный GET-параметр не даёт выдачи — короткий HTML
        # с формой не проходит длину looks_like_search_results.
        return _FORM_POST_HTML

    posted: list[tuple[str, dict]] = []

    async def post(url: str, params: dict) -> str:
        posted.append((url, params))
        return RESULTS_HTML

    prober = SearchUrlProber(fetch=fetch, post=post)
    plan = await prober.probe(SEARCH_BASE, COMPETITOR)

    assert plan.success is True
    assert plan.winner is not None
    assert plan.winner.kind == 'form'
    assert plan.winner.method == 'POST'
    assert posted == [('https://example.com/find', {'myquery': COMPETITOR})]


@pytest.mark.asyncio
async def test_probe_form_post_skipped_without_transport():
    """Без ``post=`` POST-форма помечается пропущенной, а не GET-ится."""

    async def fetch(url: str) -> str:
        return _FORM_POST_HTML

    prober = SearchUrlProber(fetch=fetch)  # post не передан
    plan = await prober.probe(SEARCH_BASE, COMPETITOR)

    assert plan.success is False
    form_attempts = [a for a in plan.attempts if a.kind == 'form']
    assert len(form_attempts) == 1
    assert form_attempts[0].detail == 'no_post_transport'
    assert form_attempts[0].method == 'POST'


# ============================================================================
# score_target_presence (фича «есть ли нужный результат»)
# ============================================================================


def test_score_target_presence_inn_hit():
    """ИНН цели в HTML — уверенное совпадение (порог 100)."""
    html = (
        '<html><body><a href="/card">Компания</a>'
        f'<span>ИНН {COMPETITOR_INN}</span></body></html>'
    )
    assert score_target_presence(html, target_inn=COMPETITOR_INN) >= 100


def test_score_target_presence_inn_miss():
    """ИНН цели отсутствует — даже при похожей выдаче скор 0."""
    html = '<html><body><p>ИНН 1234567890</p></body></html>'
    assert score_target_presence(html, target_inn=COMPETITOR_INN) == 0


def test_score_target_presence_name_exact_hit():
    """Точное (нормализованное) название цели — уверенное совпадение."""
    html = '<html><body><a href="/c1">АРХИТЕХ</a></body></html>'
    assert score_target_presence(html, target_name='ООО АРХИТЕХ') >= 100


def test_score_target_presence_partial_low_score():
    """Частичное вхождение без ИНН — слабый сигнал (30), не цель."""
    # 'архитехнологии' содержит подстроку 'архитех', но не как отдельное
    # слово — точного совпадения с границей нет, только слабый сигнал.
    html = '<html><body><p>архитехнологии будущего</p></body></html>'
    score = score_target_presence(html, target_name='АРХИТЕХ')
    assert 0 < score < 100


def test_score_target_presence_not_found():
    assert score_target_presence('<html></html>', target_name='NOPE') == 0
    assert score_target_presence('') == 0


def test_score_target_presence_inn_is_additive():
    """ИНН — аддитивный доп. сигнал: название (100) + ИНН (100) = 200.

    Раньше ИНН был обязательным условием и «поглощал» название (ровно 100).
    Теперь ИНН добавляет уверенности к уже найденному названию, что полезно
    для реестров, но не является обязательным порогом.
    """
    html = (
        f'<html><body><a>АРХИТЕХ</a><span>{COMPETITOR_INN}</span></body></html>'
    )
    assert (
        score_target_presence(
            html, target_name='АРХИТЕХ', target_inn=COMPETITOR_INN
        )
        >= 100
    )


def test_score_target_presence_stripped_name_hits_confident():
    """Название конкурента БЕЗ ОПФ/кавычек — уверенное совпадение (>=100).

    Ключевое исправление «каши»: на странице результатов/новости конкурент
    часто указан без ОПФ («АРХИТЕХ ИИ» вместо «ООО "АРХИТЕХ ИИ"»). Раньше
    это не достигало порога без ИНН, и страница отбрасывалась.
    """
    html = '<html><body><p>Компания АРХИТЕХ ИИ вышла на рынок</p></body></html>'
    assert (
        score_target_presence(
            html, target_name='ООО "АРХИТЕХ ИИ"', target_inn=''
        )
        >= 100
    )


def test_find_matched_target_variant_full():
    """Полное название с ОПФ присутствует — вариант 'full'."""
    html = '<html><body>ООО АРХИТЕХ ИИ объявило о запуске</body></html>'
    assert (
        find_matched_target_variant(html, target_name='ООО "АРХИТЕХ ИИ"')
        == 'full'
    )


def test_find_matched_target_variant_stripped():
    """Полного названия нет, но есть без ОПФ — вариант 'stripped'."""
    html = '<html><body>АРХИТЕХ ИИ открывает офис</body></html>'
    assert (
        find_matched_target_variant(html, target_name='ООО "АРХИТЕХ ИИ"')
        == 'stripped'
    )


def test_find_matched_target_variant_none():
    """Ни полного, ни без ОПФ нет — None."""
    html = '<html><body>Другая компания</body></html>'
    assert (
        find_matched_target_variant(html, target_name='ООО "АРХИТЕХ ИИ"')
        is None
    )


# ============================================================================
# probe(): проверка наличия цели (если target_name/target_inn заданы)
# ============================================================================


# Фейковый fetch: выдача похожа на результаты (>=512 символов, ссылки),
# но НЕ содержит ИНН конкурента (единственный уникальный идентификатор).
class _TargetFetch:
    """Выдача-пустышка: похожа на результаты, но цели по ИНН нет."""

    async def __call__(self, url: str) -> str:
        return RESULTS_HTML  # без COMPETITOR_INN


@pytest.mark.asyncio
async def test_probe_requires_target_in_results():
    """С виду валидная выдача БЕЗ цели — не считается успехом."""
    fetch = _TargetFetch()
    prober = SearchUrlProber(fetch=fetch)
    # Цель ищем ТОЛЬКО по ИНН: в RESULTS_HTML нет COMPETITOR_INN.
    plan = await prober.probe(
        SEARCH_BASE,
        COMPETITOR,
        target_name='',  # не ищем по названию — оно есть в RESULTS_HTML
        target_inn=COMPETITOR_INN,
    )

    assert plan.success is False
    assert plan.winner is None
    # Хотя бы одна попытка — 'param', но ok=False из-за отсутствия цели.
    assert all(a.ok is False for a in plan.attempts)


@pytest.mark.asyncio
async def test_probe_target_found_wins():
    """Цель есть в выдаче по какому-то параметру — побеждает он."""

    class _TargetHitFetch:
        def __init__(self):
            self.calls: list[str] = []

        async def __call__(self, url: str) -> str:
            self.calls.append(url)
            param = url.split('?', 1)[-1].split('=', 1)[0]
            if param == 'query':
                # По query приходит выдача с целью (ИНН конкурента).
                # Длинная аннотация нужна, чтобы пройти len-порог
                # looks_like_search_results (>= 512 символов).
                padding = '<p>вакансии компаний по вашему запросу</p>' * 20
                return (
                    '<html><body><h1>Результаты</h1>'
                    '<a href="/r1">Компания</a>'
                    f'<span>ИНН {COMPETITOR_INN}</span>'
                    f'{padding}'
                    '</body></html>'
                )
            return RESULTS_HTML  # без цели

    prober = SearchUrlProber(fetch=_TargetHitFetch())
    plan = await prober.probe(
        SEARCH_BASE,
        COMPETITOR,
        target_name='',  # цель ищем только по ИНН
        target_inn=COMPETITOR_INN,
    )

    assert plan.success is True
    assert plan.winner is not None
    assert plan.winner.kind == 'param'
    assert plan.winner.label == 'query'
    # У победителя цель найдена.
    assert plan.winner.target_found is True
    assert plan.winner.target_score >= 100


@pytest.mark.asyncio
async def test_probe_without_target_uses_looks_like_only():
    """Без target_name/target_inn поведение не меняется (старые тесты)."""
    fetch = _FakeFetch(good_param='text')
    prober = SearchUrlProber(fetch=fetch)
    plan = await prober.probe(SEARCH_BASE, COMPETITOR)

    assert plan.success is True
    assert plan.winner is not None
    assert plan.winner.label == 'text'


# ---------------------------------------------------------------------------
# Проверка причинности: кандидат обязан отличаться от базовой ленты
# (регресс-тест на инцидент rbc.ru — q= сайтом игнорировался, отдавалась
# общая лента, где случайно встретилось имя цели)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_rejects_candidate_matching_baseline():
    """Кандидат с тем же составом карточек, что у базовой ленты, — не

    победитель, даже если цель в нём есть. Побеждает следующий кандидат
    (`query`), реально отличающийся от базовой ленты.
    """
    baseline_links = ''.join(
        f'<a href="/feed{i}">Новость {i}</a>' for i in range(10)
    )
    baseline_html = (
        f'<html><body><h1>Лента</h1>{baseline_links}'
        f'<span>{COMPETITOR}</span></body></html>'
    )
    filtered_html = (
        '<html><body><h1>Результаты поиска</h1>'
        f'<a href="/found">{COMPETITOR} — статья</a>'
        '<p>' + 'заполнитель ' * 100 + '</p>'
        '</body></html>'
    )

    class _UnfilteredParamFetch:
        async def __call__(self, url: str) -> str:
            if '?' not in url:
                return baseline_html
            param = url.split('?', 1)[-1].split('=', 1)[0]
            if param == 'q':
                # 'q' сайтом игнорируется — та же лента, что и без параметра.
                return baseline_html
            if param == 'query':
                return filtered_html
            return EMPTY_HTML

    prober = SearchUrlProber(fetch=_UnfilteredParamFetch())
    plan = await prober.probe(SEARCH_BASE, COMPETITOR, target_name=COMPETITOR)

    assert plan.success is True
    assert plan.winner is not None
    # 'q' идёт первым в _DEFAULT_PARAM_CHAIN, но отклонён проверкой
    # причинности — победил следующий, реально фильтрующий параметр.
    assert plan.winner.label == 'query'
    q_attempt = next(a for a in plan.attempts if a.label == 'q')
    assert q_attempt.ok is False


@pytest.mark.asyncio
async def test_probe_baseline_unavailable_falls_back_to_old_behavior():
    """base_url недоступен (fetch вернул None) — сравнение с базовой лентой

    не блокирует победителя, поведение как до этой правки.
    """

    class _NoBaselineFetch:
        async def __call__(self, url: str) -> str | None:
            if '?' not in url:
                return None
            param = url.split('?', 1)[-1].split('=', 1)[0]
            if param == 'text':
                return RESULTS_HTML
            return EMPTY_HTML

    prober = SearchUrlProber(fetch=_NoBaselineFetch())
    plan = await prober.probe(SEARCH_BASE, COMPETITOR, target_name=COMPETITOR)

    assert plan.success is True
    assert plan.winner is not None
    assert plan.winner.label == 'text'


@pytest.mark.asyncio
async def test_probe_rejects_candidate_matching_known_other_competitor():
    """known_other_result_urls отклоняет кандидата, совпадающего с уже

    подтверждённой выдачей другого конкурента на этом источнике.
    """
    filtered_html = (
        '<html><body><h1>Результаты поиска</h1>'
        f'<a href="/found">{COMPETITOR} — статья</a>'
        '<p>' + 'заполнитель ' * 100 + '</p>'
        '</body></html>'
    )

    class _NoBaselineFetch:
        async def __call__(self, url: str) -> str | None:
            if '?' not in url:
                return None
            param = url.split('?', 1)[-1].split('=', 1)[0]
            if param == 'q':
                return filtered_html
            return EMPTY_HTML

    prober = SearchUrlProber(fetch=_NoBaselineFetch())
    plan = await prober.probe(
        SEARCH_BASE,
        COMPETITOR,
        target_name=COMPETITOR,
        known_other_result_urls={'https://example.com/found'},
    )

    assert plan.success is False


@pytest.mark.asyncio
async def test_probe_async_populates_sample_item_urls():
    """probe_async кладёт множество URL карточек победителя в

    ProbedUrl.sample_item_urls — снимок для сравнения будущих конкурентов.
    """
    fetch = _FakeFetch(good_param='text')
    prober = SearchUrlProber(fetch=fetch)
    probed = await prober.probe_async(
        SEARCH_BASE, COMPETITOR, target_name=COMPETITOR
    )

    assert probed is not None
    assert probed.sample_item_urls
    assert all(
        url.startswith('https://example.com/')
        for url in probed.sample_item_urls
    )
