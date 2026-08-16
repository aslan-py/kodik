"""
Перебор вариантов поискового запроса с проверкой наличия цели в выдаче.

Проблема: один поисковый запрос (параметр -> форма -> реформулировки) не
всегда даёт выдачу, где есть нужный результат (компания-конкурент). Сайт
может вернуть пустую выдачу, «ничего не найдено» или результаты по другому
запросу.

Решение: ``SearchUrlProber`` перебирает варианты запроса по порядку и после
каждого ответа проверяет, есть ли в HTML выдачи строка, которую мы отправили
в поиск (``search_query``). Совпадение строки — самый явный признак, что
вариант поиска правильный: берём его. Если цели в выдаче нет — переходим к
следующему варианту.

Проверка цели — case-insensitive: обе строки приводятся к нижнему регистру
с заменой ``ё`` на ``е`` (многие сайты пишут «е» вместо «ё»). Никакой
нормализации названия (ОПФ, кавычки, тире) и границ слова нет — ищем ровно
ту строку, что передали в ``search``.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlsplit

from ..schemas import ProbedUrl

logger = logging.getLogger(__name__)

# Таймаут (в секундах) на пробинг одного URL. Защищает конвейер от зависания
# на неотвечающем источнике при вызове ``probe_async``.
DEFAULT_PROBE_TIMEOUT_SECONDS = 10.0

# Порог уверенности: цель считается найденной, если оценка >= порога.
_TARGET_CONFIDENT = 100

# Организационно-правовые формы, которые отбрасываются при переформулировке
# запроса: на большинстве сайтов компания упоминается без ОПФ
# («АРХИТЕХ», а не «ООО АРХИТЕХ»).
_LEGAL_FORM_PREFIXES = (
    'ооо',
    'зао',
    'оао',
    'пао',
    'ао',
    'ип',
    'нко',
    'ано',
    'фгуп',
    'гуп',
    'муп',
)

# Кавычки всех видов, встречающиеся в названиях компаний.
_QUOTES = '«»""\'\'"'


def _strip_legal_form(name: str) -> str:
    """Убирает ведущую организационно-правовую форму из названия."""
    parts = name.split()
    if parts and _fold(parts[0]).strip(_QUOTES) in _LEGAL_FORM_PREFIXES:
        return ' '.join(parts[1:])
    return name


def build_reformulations(search_query: str, limit: int) -> list[str]:
    """Строит варианты поискового запроса (переформулировки).

    Раньше этап переформулировок был заглушкой: он ``limit`` раз повторял
    ровно тот же URL, что и предыдущий этап, — то есть не менял запрос
    вообще (Шаг 18 плана рефакторинга, REFACTORING_PLAN.md).

    Варианты по убыванию точности:

    1. Без кавычек: ``ООО «АРХИТЕХ»`` -> ``ООО АРХИТЕХ``.
    2. Без ОПФ: ``ООО АРХИТЕХ`` -> ``АРХИТЕХ`` (большинство сайтов
       упоминают компанию без организационно-правовой формы).
    3. Без ОПФ и кавычек одновременно.
    4. Только первое значимое слово: ``АРХИТЕХ ИИ`` -> ``АРХИТЕХ``
       (самый широкий запрос — последняя попытка).

    Дубликаты и пустые строки отбрасываются, исходный запрос в список не
    попадает (он уже проверен на предыдущих этапах).

    Args:
        search_query: Исходная строка поиска.
        limit: Максимальное число вариантов.

    Returns:
        Список уникальных переформулировок (может быть пустым, если
        запрос не поддаётся упрощению — например, одно слово без ОПФ).
    """
    if not search_query or limit <= 0:
        return []

    no_quotes = re.sub(f'[{re.escape(_QUOTES)}]', '', search_query)
    no_quotes = ' '.join(no_quotes.split())

    candidates = [
        no_quotes,
        _strip_legal_form(search_query),
        _strip_legal_form(no_quotes),
    ]

    first_word = _strip_legal_form(no_quotes).split()
    if first_word:
        candidates.append(first_word[0])

    seen = {_fold(search_query)}
    variants: list[str] = []
    for candidate in candidates:
        cleaned = candidate.strip()
        key = _fold(cleaned)
        if not cleaned or key in seen:
            continue
        seen.add(key)
        variants.append(cleaned)
        if len(variants) >= limit:
            break
    return variants


def _search_endpoint(base_url: str) -> str:
    """Возвращает URL поиска без query-строки (``scheme://host/path``).

    Нужен, чтобы строить параметрические варианты (``?q=``, ``?text=``)
    независимо от того, какой параметр зашит в шаблон источника.
    """
    split = urlsplit(base_url)
    scheme = split.scheme or 'https'
    return f'{scheme}://{split.netloc}{split.path}'


def _template_param(base_url: str) -> str | None:
    """Имя query-параметра из шаблона источника (если он там задан).

    ``https://hh.ru/search/vacancy?text={q}`` -> ``text``. Используется как
    первый кандидат перебора: per-source шаблон
    (``SearchUrlTemplateRegistry``) — самое достоверное знание о том, какой
    параметр понимает конкретный сайт. Плейсхолдер ``{q}``, стоящий на
    месте ИМЕНИ параметра (``?{q}=``), именем не считается.
    """
    query = urlsplit(base_url).query
    if not query:
        return None
    for name, _value in parse_qsl(query, keep_blank_values=True):
        if name and '{q}' not in name:
            return name
    return None


def _build_param_url(base_url: str, param: str, value: str) -> str:
    """Строит GET-URL поиска с заданным именем параметра и значением.

    Раньше параметрический перебор делал ``base_url.replace('{q}', param)``,
    подставляя ИМЯ параметра на место ЗНАЧЕНИЯ: для рантайм-шаблона
    ``?text={q}`` получался запрос ``?text=q`` — поиск литерала «q» вместо
    названия компании (Шаг 18 плана рефакторинга). Теперь URL собирается
    из эндпоинта шаблона и пары ``param=value`` явно.
    """
    return f'{_search_endpoint(base_url)}?{param}={quote_plus(value)}'


def _fold(text: str) -> str:
    """Приводит текст к нижнему регистру с заменой ``ё`` на ``е``.

    Используется для case-insensitive сравнения: ``АРХИТЕХ``, ``Архитех``
    и ``архитех`` считаются одним словом, ``Берёза`` == ``Береза``.
    """
    return text.lower().replace('ё', 'е')


def score_target_presence(html: str, search_query: str) -> int:
    """Оценивает, есть ли цель (строка поиска) в HTML выдачи.

    Правило: ищем ровно ту строку, что передали в ``search``, без
    нормализации названия (ОПФ, кавычки, тире) и без границ слова.
    Сравнение case-insensitive (нижний регистр + замена ``ё`` на ``е``).

    Возвращает ``_TARGET_CONFIDENT`` (100), если строка найдена, иначе 0.
    Пустой ``search_query`` — цель не задана, всегда 0.
    """
    if not search_query:
        return 0
    return _TARGET_CONFIDENT if _fold(search_query) in _fold(html) else 0


@dataclass
class ProbeAttempt:
    """Одна попытка поиска (вариант запроса)."""

    kind: str  # 'param' | 'form' | 'reformulation'
    label: str
    url: str
    ok: bool
    detail: str = ''
    target_found: bool = False
    target_score: int = 0
    # Фактические параметры запроса ``{имя: значение}`` — то, что реально
    # ушло на сайт. Раньше в ``ProbedUrl.search_params`` попадало
    # ``{label: detail}``, то есть имя параметра и СТАТУС попытки
    # ('ok'/'empty_results') вместо значения (Шаг 18 плана рефакторинга).
    params: dict[str, str] = field(default_factory=dict)
    # HTTP-метод попытки: 'GET' для параметров/переформулировок, 'POST'
    # для формы. Раньше метод угадывался по ``kind`` в
    # ``_attempt_to_probed``, из-за чего form-попытка, выполненная через
    # GET, помечалась как POST.
    method: str = 'GET'


@dataclass
class ProbePlan:
    """План перебора вариантов поиска (список попыток)."""

    attempts: list[ProbeAttempt] = field(default_factory=list)

    def add(
        self,
        kind: str,
        label: str,
        url: str,
        ok: bool,
        detail: str = '',
        target_found: bool = False,
        target_score: int = 0,
        params: dict[str, str] | None = None,
        method: str = 'GET',
    ) -> None:
        """Добавляет попытку в план."""
        self.attempts.append(
            ProbeAttempt(
                kind=kind,
                label=label,
                url=url,
                ok=ok,
                detail=detail,
                target_found=target_found,
                target_score=target_score,
                params=params or {},
                method=method,
            )
        )

    def to_extra(self) -> dict[str, Any]:
        """Возвращает план в виде словаря для ``extra`` отчёта."""
        return {
            'probe_attempts': [
                {
                    'kind': a.kind,
                    'label': a.label,
                    'url': a.url,
                    'ok': a.ok,
                    'detail': a.detail,
                    'target_found': a.target_found,
                    'target_score': a.target_score,
                    'method': a.method,
                }
                for a in self.attempts
            ]
        }


class SearchUrlProber:
    """Перебирает варианты поискового запроса и проверяет наличие цели.

    Порядок перебора: параметры (``q``, ``query``, ``text``, ...) -> форма
    (POST) -> реформулировки (уточнения запроса). После каждого ответа
    проверяется ``looks_like_search_results`` (похоже ли на выдачу) и, если
    задана цель (``target_name``), — ``score_target_presence`` (есть ли
    строка поиска в HTML). Если цели нет — попытка помечается неуспешной
    (``ok=False``, ``detail='empty_results'``) и перебор идёт дальше.
    """

    # Параметры поиска, которые пробуем по порядку (в порядке убывания
    # популярности). Первый параметр — самый вероятный.
    _DEFAULT_PARAM_CHAIN = (
        'q',
        'query',
        'text',
        'search',
        'keyword',
        'keywords',
        'searchText',
        'searchQuery',
        'search_string',
        'search_query',
        'find',
        'findText',
        'searchString',
        'searchword',
        'keys',
        'term',
        'terms',
        'qry',
        'srch',
        'searchStr',
        'searchtext',
        'searchKeyword',
        'do',
        'sentance',
        'keywordsearch',
    )

    def __init__(
        self,
        fetch: Callable[[str], str] | None = None,
        looks_like_search_results: Callable[[str], bool] | None = None,
        param_chain: tuple[str, ...] | None = None,
        max_params: int = 7,
        max_reformulations: int = 5,
        post: Callable[[str, dict[str, str]], str] | None = None,
    ) -> None:
        self._fetch = fetch or self._default_fetch
        self._looks_like = looks_like_search_results or self._default_looks_like
        self._param_chain = param_chain or self._DEFAULT_PARAM_CHAIN
        self._max_params = max_params
        self._max_reformulations = max_reformulations
        # Транспорт для POST-формы (Шаг 18 плана рефакторинга). Опционален:
        # если не задан, этап формы честно помечается как пропущенный
        # ('no_post_transport'), а не имитируется GET-запросом, как раньше.
        self._post = post

    @staticmethod
    def _default_fetch(url: str) -> str:
        """Заглушка: реальный fetch подставляется в рантайме."""
        raise NotImplementedError(
            'SearchUrlProber требует fetch-функцию (передайте в конструктор)'
        )

    @staticmethod
    def _default_looks_like(html: str) -> bool:
        """Заглушка: реальная проверка подставляется в рантайме."""
        raise NotImplementedError(
            'SearchUrlProber требует looks_like_search_results '
            '(передайте в конструктор)'
        )

    def probe(
        self,
        base_url: str,
        search_query: str,
        *,
        prefer_param: str | None = None,
        target_name: str = '',
    ) -> ProbePlan:
        """Перебирает варианты поиска и возвращает план попыток.

        ``base_url`` — URL поиска с плейсхолдером ``{q}`` (например,
        ``https://hh.ru/search/vacancy?text={q}``). ``search_query`` — строка,
        которую подставляем в ``{q}`` и которую ищем в выдаче (цель).
        ``prefer_param`` — параметр, который пробуем первым (если известен).
        """
        plan = ProbePlan()

        # 1. Параметры: пробуем по порядку, начиная с предпочтительного.
        #    Если предпочтительный не задан явно, берём параметр из шаблона
        #    источника (SearchUrlTemplateRegistry): для hh.ru это 'text' —
        #    самое достоверное знание о конкретном сайте.
        preferred = prefer_param or _template_param(base_url)
        params = self._ordered_params(preferred)
        for param in params[: self._max_params]:
            url = _build_param_url(base_url, param, search_query)
            if self._record_get(
                plan,
                kind='param',
                label=param,
                url=url,
                params={param: search_query},
                query=search_query,
                target_name=target_name,
            ):
                return plan

        # 2. Форма: настоящий POST-запрос на эндпоинт поиска.
        if self._probe_form(
            plan, base_url, search_query, preferred, target_name
        ):
            return plan

        # 3. Переформулировки: упрощённые варианты запроса (без кавычек,
        #    без ОПФ, первое значимое слово) — GET по предпочтительному
        #    параметру.
        variants = build_reformulations(search_query, self._max_reformulations)
        param = preferred or (
            self._param_chain[0] if self._param_chain else 'q'
        )
        for i, variant in enumerate(variants):
            url = _build_param_url(base_url, param, variant)
            if self._record_get(
                plan,
                kind='reformulation',
                label=f'reformulation-{i}:{variant}',
                url=url,
                params={param: variant},
                # Проверяем присутствие того, что реально искали.
                query=variant,
                target_name=target_name,
            ):
                return plan

        return plan

    def _record_get(
        self,
        plan: ProbePlan,
        *,
        kind: str,
        label: str,
        url: str,
        params: dict[str, str],
        query: str,
        target_name: str,
    ) -> bool:
        """Выполняет GET-попытку и записывает её в план.

        Общая логика для параметрических попыток и переформулировок:
        загрузить, проверить «похоже ли на выдачу», проверить наличие цели.

        Returns:
            True, если попытка успешна (перебор можно остановить).
        """
        html = self._safe_fetch(url)
        if html is None:
            plan.add(
                kind, label, url, ok=False, detail='fetch_error', params=params
            )
            return False
        if not self._looks_like(html):
            plan.add(
                kind,
                label,
                url,
                ok=False,
                detail='not_search_results',
                params=params,
            )
            return False

        score = score_target_presence(html, query)
        if target_name and score < _TARGET_CONFIDENT:
            plan.add(
                kind,
                label,
                url,
                ok=False,
                detail='empty_results',
                target_found=False,
                target_score=score,
                params=params,
            )
            return False

        plan.add(
            kind,
            label,
            url,
            ok=True,
            detail='ok',
            target_found=bool(target_name),
            target_score=score,
            params=params,
        )
        return True

    def _probe_form(
        self,
        plan: ProbePlan,
        base_url: str,
        search_query: str,
        preferred: str | None,
        target_name: str,
    ) -> bool:
        """Пробует отправить поиск POST-формой на эндпоинт источника.

        Раньше этот этап был заглушкой: он выполнял обычный GET того же
        URL, что и параметрический перебор, но результат помечался как
        ``search_method='POST'`` (Шаг 18 плана рефакторинга). Теперь при
        отсутствии POST-транспорта этап честно пропускается, а при наличии
        выполняется настоящий POST с телом ``{param: search_query}``.

        Returns:
            True, если форма дала успешный результат.
        """
        form_url = _search_endpoint(base_url)
        param = preferred or (
            self._param_chain[0] if self._param_chain else 'q'
        )
        params = {param: search_query}

        if self._post is None:
            plan.add(
                'form',
                'form',
                form_url,
                ok=False,
                detail='no_post_transport',
                params=params,
                method='POST',
            )
            return False

        try:
            html = self._post(form_url, params)
        except Exception as e:
            logger.warning('Ошибка POST %s: %s', form_url, e)
            html = None

        if html is None or not self._looks_like(html):
            plan.add(
                'form',
                'form',
                form_url,
                ok=False,
                detail='not_search_results' if html else 'fetch_error',
                params=params,
                method='POST',
            )
            return False

        score = score_target_presence(html, search_query)
        if target_name and score < _TARGET_CONFIDENT:
            plan.add(
                'form',
                'form',
                form_url,
                ok=False,
                detail='empty_results',
                target_found=False,
                target_score=score,
                params=params,
                method='POST',
            )
            return False

        plan.add(
            'form',
            'form',
            form_url,
            ok=True,
            detail='ok',
            target_found=bool(target_name),
            target_score=score,
            params=params,
            method='POST',
        )
        return True

    async def probe_async(
        self,
        base_url: str,
        search_query: str,
        *,
        prefer_param: str | None = None,
        target_name: str = '',
    ) -> ProbedUrl | None:
        """Асинхронный пробинг: возвращает ``ProbedUrl`` или ``None``.

        Асинхронная обёртка над синхронным ``probe``: блокирующий перебор
        вариантов выполняется в отдельном потоке через ``asyncio.to_thread``
        и ограничивается таймаутом ``DEFAULT_PROBE_TIMEOUT_SECONDS``. Если
        пробинг нашёл успешную попытку (``ok=True``), из неё формируется
        ``ProbedUrl``. При отсутствии успешного варианта, таймауте или
        исключении возвращается ``None`` (fallback будет построен рантаймом).
        """
        try:
            plan = await asyncio.wait_for(
                asyncio.to_thread(
                    self.probe,
                    base_url,
                    search_query,
                    prefer_param=prefer_param,
                    target_name=target_name,
                ),
                timeout=DEFAULT_PROBE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                'Таймаут пробинга %s (query=%r)', base_url, search_query
            )
            return None
        except Exception as e:  # pragma: no cover - защита от неожиданностей
            logger.warning('Ошибка пробинга %s: %s', base_url, e)
            return None

        for attempt in plan.attempts:
            if attempt.ok:
                return _attempt_to_probed(
                    source_name=target_name or search_query,
                    attempt=attempt,
                )
        return None

    def _ordered_params(self, prefer_param: str | None) -> list[str]:
        """Параметры по порядку: предпочтительный первым, затем цепочка."""
        if not prefer_param:
            return list(self._param_chain)
        return [prefer_param] + [
            p for p in self._param_chain if p != prefer_param
        ]

    def _safe_fetch(self, url: str) -> str | None:
        """Выполняет fetch, возвращая None при ошибке."""
        try:
            return self._fetch(url)
        except Exception as e:
            logger.warning('Ошибка fetch %s: %s', url, e)
            return None


def _attempt_to_probed(source_name: str, attempt: ProbeAttempt) -> ProbedUrl:
    """Превращает успешную попытку пробинга в ``ProbedUrl``.

    ``attempt.url`` — найденный поисковый URL (для GET — уже с подставленным
    значением, для POST — эндпоинт формы), ``attempt.params`` — фактические
    параметры запроса, ``attempt.method`` — реально использованный HTTP-метод.

    Раньше метод угадывался по ``kind`` (form-попытка, выполненная через GET,
    помечалась как POST), а в ``search_params`` вместо значения попадал
    статус попытки (``{'q': 'ok'}``) — см. Шаг 18 плана рефакторинга.
    """
    return ProbedUrl(
        source_name=source_name,
        search_url=attempt.url,
        search_method=attempt.method,
        search_params=dict(attempt.params),
        result_count_selector=None,
        confidence=(
            attempt.target_score / _TARGET_CONFIDENT
            if attempt.target_found
            else 1.0
        ),
        probed_at=datetime.now(UTC),
    )
