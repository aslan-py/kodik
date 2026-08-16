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
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..schemas import ProbedUrl

logger = logging.getLogger(__name__)

# Таймаут (в секундах) на пробинг одного URL. Защищает конвейер от зависания
# на неотвечающем источнике при вызове ``probe_async``.
DEFAULT_PROBE_TIMEOUT_SECONDS = 10.0

# Порог уверенности: цель считается найденной, если оценка >= порога.
_TARGET_CONFIDENT = 100


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
    ) -> None:
        self._fetch = fetch or self._default_fetch
        self._looks_like = looks_like_search_results or self._default_looks_like
        self._param_chain = param_chain or self._DEFAULT_PARAM_CHAIN
        self._max_params = max_params
        self._max_reformulations = max_reformulations

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
        params = self._ordered_params(prefer_param)
        for param in params[: self._max_params]:
            url = base_url.replace('{q}', param)
            html = self._safe_fetch(url)
            if html is None:
                plan.add(
                    'param',
                    param,
                    url,
                    ok=False,
                    detail='fetch_error',
                )
                continue
            if not self._looks_like(html):
                plan.add(
                    'param',
                    param,
                    url,
                    ok=False,
                    detail='not_search_results',
                )
                continue
            score = score_target_presence(html, search_query)
            if target_name and score < _TARGET_CONFIDENT:
                plan.add(
                    'param',
                    param,
                    url,
                    ok=False,
                    detail='empty_results',
                    target_found=False,
                    target_score=score,
                )
                continue
            plan.add(
                'param',
                param,
                url,
                ok=True,
                detail='ok',
                target_found=bool(target_name),
                target_score=score,
            )
            return plan

        # 2. Форма: POST-запрос (заглушка — реальная логика в рантайме).
        form_url = base_url.replace('{q}', search_query)
        html = self._safe_fetch(form_url)
        if html is not None and self._looks_like(html):
            score = score_target_presence(html, search_query)
            if not target_name or score >= _TARGET_CONFIDENT:
                plan.add(
                    'form',
                    'form',
                    form_url,
                    ok=True,
                    detail='ok',
                    target_found=bool(target_name),
                    target_score=score,
                )
                return plan
            plan.add(
                'form',
                'form',
                form_url,
                ok=False,
                detail='empty_results',
                target_found=False,
                target_score=score,
            )
        else:
            plan.add(
                'form',
                'form',
                form_url,
                ok=False,
                detail='not_search_results',
            )

        # 3. Реформулировки: уточнения запроса (заглушка — реальная логика
        #    в рантайме).
        for i in range(self._max_reformulations):
            reform_url = base_url.replace('{q}', search_query)
            html = self._safe_fetch(reform_url)
            if html is None:
                plan.add(
                    'reformulation',
                    f'reformulation-{i}',
                    reform_url,
                    ok=False,
                    detail='fetch_error',
                )
                continue
            if not self._looks_like(html):
                plan.add(
                    'reformulation',
                    f'reformulation-{i}',
                    reform_url,
                    ok=False,
                    detail='not_search_results',
                )
                continue
            score = score_target_presence(html, search_query)
            if target_name and score < _TARGET_CONFIDENT:
                plan.add(
                    'reformulation',
                    f'reformulation-{i}',
                    reform_url,
                    ok=False,
                    detail='empty_results',
                    target_found=False,
                    target_score=score,
                )
                continue
            plan.add(
                'reformulation',
                f'reformulation-{i}',
                reform_url,
                ok=True,
                detail='ok',
                target_found=bool(target_name),
                target_score=score,
            )
            return plan

        return plan

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

    ``attempt.url`` — явно найденный успешный поисковый URL (уже с
    подставленным параметром), ``attempt.label`` — имя параметра GET-запроса
    (например ``q``), ``search_method`` — для попыток вида ``param``/``form``.
    """
    return ProbedUrl(
        source_name=source_name,
        search_url=attempt.url,
        search_method='POST' if attempt.kind == 'form' else 'GET',
        search_params={attempt.label: attempt.detail or ''}
        if attempt.kind in ('param', 'form')
        else {},
        result_count_selector=None,
        confidence=(
            attempt.target_score / _TARGET_CONFIDENT
            if attempt.target_found
            else 1.0
        ),
        probed_at=datetime.now(UTC),
    )
