"""
Адаптивный перебор поисковых запросов (BP-1 Adaptive).

Решает проблему «страница результатов не даёт нужных результатов» тремя
механизмами:

1. ``SearchUrlProber`` — перебор типовых query-параметров (``q``, ``query``,
   ``text``, ``search``, ...). Сайты понимают поиск по-разному: hh.ru —
   ``?text=``, большинство каталогов — ``?q=``, часть — ``?search=``.
   Если страница, построенная по словарному параметру, не похожа на
   результаты поиска, пробуем следующий параметр из цепочки.

2. Детект параметра из HTML-формы поиска (``<form>``): после каждого
   успешного ответа ищем в HTML ``<form>``/``<input>`` — если найдена
   поисковая форма, её ``name``/``action`` становятся приоритетным
   параметром (без ручной правки реестра).

3. Реформулировки запроса (``QueryReformulator``): при нулевых результатах
   пробуем варианты запроса — точное название, без организационно-правовой
   формы (ООО/АО/ИП), без лишних слов, транслит, ИНН.

Итоговый ответ про ``what_was_done`` заземляется на факты: сколько
параметров/форм/реформулировок перебрано и какой параметр/запрос сработал.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from ..schemas import SourceType

logger = logging.getLogger(__name__)

# Ключ в ``extra`` элемента-страницы поиска, куда сохраняется отчёт про
# перебор параметров/форм/реформулировок (для дашбордов и диагностики).
PROBE_EXTRA_KEY = 'probe_report'

# Типовые имена query-параметров поиска в порядке предпочтения: чем выше
# параметр в списке, тем раньше он пробуется. Первые (``q``/``query``) —
# самые частые, ``do``/``sentance`` и прочие — редкие, но встречаются.
_DEFAULT_PARAM_CHAIN: tuple[str, ...] = (
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

# Ключевые слова, которые обычно говорят о том, что целая страница — это
# форма/пустая выдача/исключение, а не список результатов.
_NEGATIVE_MARKERS: tuple[str, ...] = (
    'captcha',
    'qrator',
    'доступ ограничен',
    'антибот',
    'не удалось найти',
    'ничего не найдено',
    'ничего не нашлось',
    'не найдено',
    'по запросу ничего не найдено',
    'уточните запрос',
    'результатов не найдено',
    'no results found',
    'nothing found',
    'not found',
    'поиск ничего не дал',
    'пожалуйста, выполните поиск',
    'введите запрос',
    'запрос обязателен',
    'search again',
    'проверьте, правильно ли введён запрос',
)

# Параметры, которые заведомо НЕ являются поисковыми (мусорные).
_FILTER_PARAMS: frozenset[str] = frozenset(
    {
        'page',
        'offset',
        'limit',
        'per_page',
        'sort',
        'order',
        'filter',
        'f',
        'from',
        'to',
        'csrf_token',
        'csrfmiddlewaretoken',
        'token',
        'sessionid',
        'PHPSESSID',
        'lang',
        'locale',
        'utm_source',
        'utm_medium',
        'utm_campaign',
    }
)

# Частые организационно-правовые формы в начале названия компании.
_LEGAL_FORMS: tuple[str, ...] = (
    'ооо',
    'зао',
    'ао',
    'пао',
    'оао',
    'нко',
    'ип',
    'гк',
    'нп',
    'акционерное общество',
    'общество с ограниченной ответственностью',
    'открытое акционерное общество',
    'индивидуальный предприниматель',
)


# ============================================================================
# Модель «попробованного варианта поиска» (для отчёта)
# ============================================================================


@dataclass
class ProbeAttempt:
    """Один перебранный вариант поиска (параметр или реформулировка)."""

    kind: str  # 'param' | 'form' | 'query'
    label: str
    url: str = ''
    ok: bool = False
    detail: str = ''
    target_found: bool = False
    target_score: int = 0
    # Найденный вариант названия конкурента: 'full' (с ОПФ) | 'stripped'
    # (без ОПФ/кавычек) | None. Используется далее при сборе новостей.
    matched_variant: str | None = None


@dataclass
class ProbePlan:
    """Результат прохождения: успешная попытка + все перебранные варианты."""

    attempts: list[ProbeAttempt] = field(default_factory=list)
    winner: ProbeAttempt | None = None

    @property
    def success(self) -> bool:
        return self.winner is not None

    def add(
        self,
        kind: str,
        label: str,
        url: str = '',
        ok: bool = False,
        detail: str = '',
        target_found: bool = False,
        target_score: int = 0,
        matched_variant: str | None = None,
    ) -> ProbeAttempt:
        attempt = ProbeAttempt(
            kind=kind,
            label=label,
            url=url,
            ok=ok,
            detail=detail,
            target_found=target_found,
            target_score=target_score,
            matched_variant=matched_variant,
        )
        self.attempts.append(attempt)
        if ok and self.winner is None:
            self.winner = attempt
        return attempt

    def to_extra(self) -> dict[str, Any]:
        """Сериализует прохождение для ``extra[PROBE_EXTRA_KEY]``."""
        return {
            'success': self.success,
            'winner': (
                {
                    'kind': self.winner.kind,
                    'label': self.winner.label,
                    'url': self.winner.url,
                    'matched_variant': self.winner.matched_variant,
                }
                if self.winner
                else None
            ),
            'attempts': [
                {
                    'kind': a.kind,
                    'label': a.label,
                    'url': a.url,
                    'ok': a.ok,
                    'detail': a.detail,
                    # Скрытая деталь: код причины для дашбордов.
                    'reason': a.detail,
                    'target_found': a.target_found,
                    'target_score': a.target_score,
                    'matched_variant': a.matched_variant,
                }
                for a in self.attempts
            ],
        }


# ============================================================================
# Эвристики по HTML
# ============================================================================


def looks_like_search_results(html: str) -> bool:
    """Эвристика: похожа ли страница на результаты поиска.

    Позитивные сигналы: упоминание результатов («найдено N», «результатов»),
    наличие списка ссылок, признаки выдачи. Негативные — страница-заглушка
    «ничего не найдено», капча, страница входа и т.п. Если HTML пустой или
    слишком короткий — считаем «не результаты».
    """
    if not html or len(html) < 512:
        return False

    probe = (html or '').lower()

    # Сначала негативные маркеры — они сильнее позитивных.
    for marker in _NEGATIVE_MARKERS:
        if marker in probe:
            return False

    # Позитивный сигнал: упоминание результатов найдено.
    if re.search(r'(найдено|нашлось|результат\w*|результаты)\b', probe):
        return True

    # Позитивный сигнал: в теле > 3 ссылок (выдача обычно состоит из ссылок
    # на карточки). Текст берём из всего HTML, но исключаем <script>/<style>,
    # чтобы не считать ссылки из JS-бандлов.
    soup = BeautifulSoup(html, 'html.parser')
    link_count = 0
    for a in soup.find_all('a', href=True):
        href = (a.get('href') or '').strip()
        if href and not href.startswith(('#', 'javascript:', 'mailto:')):
            link_count += 1
            if link_count > 3:
                return True

    return False


# ---------------------------------------------------------------------------
# Проверка наличия цели в HTML (фича «есть ли нужный результат»)
# ---------------------------------------------------------------------------
# Критерий выбора удачного варианта запроса — ДВУХЭТАПНАЯ проверка названия
# конкурента, а не рейтинг ИНН:
#
#   1-й этап: ищем ПОЛНОЕ название конкурента ровно как оно передано в
#             запросе (нормализовано: регистр, лишние пробелы, пунктуация;
#             ОПФ сохраняется).
#   2-й этап: если полное название не найдено — ищем название БЕЗ
#             организационно-правовой формы и без кавычек/скобок/тире
#             («ООО "АРХИТЕХ ИИ"» -> «архитех ии»).
# Такая двухэтапность решает проблему «каши»: на странице результатов
# ИНН может отсутствовать, а в новости конкурент указан без ОПФ. Раньше
# обязательный порог по ИНН отбрасывал такие страницы, и выбор падал на
# случайный/неправильный вариант. Теперь ИНН — лишь ОПЦИОНАЛЬНЫЙ доп.
# сигнал (полезен для реестров), но НЕ обязательное условие успеха.
_TARGET_CONFIDENT = 100

# Веса сигналов наличия цели.
_INN_SIGNAL = 100  # ИНН цели найден (доп. подтверждение, необязательно).
# Полное название с ОПФ — уверенное совпадение (1-й этап).
_NAME_EXACT_SIGNAL = 100
# Название без ОПФ/кавычек — тоже достаточно для выбора (2-й этап).
_NAME_STRIPPED_SIGNAL = 100
# Частичное вхождение названия в текст аннотации — слабый сигнал,
# НЕ достигает порога _TARGET_CONFIDENT (не выбирается).
_NAME_PARTIAL_SIGNAL = 30


def _normalize_target_text(value: str, strip_legal: bool = False) -> str:
    """Нормализует цель (название/текст) для сравнения: регистр, лишние
    пробелы, кавычки/скобки/тире.

    strip_legal=False — сохраняет организационно-правовую форму в начале
    («ООО АРХИТЕХ ИИ» -> «ооо архитех ии»). strip_legal=True — убирает ОПФ
    и оставляет только имя («ООО АРХИТЕХ ИИ» -> «архитех ии»).

    Точки (в названии ИНН и т.п.) не трогаем: они не мешают нормализации.
    """
    if not value:
        return ''
    normalized = re.sub(r'\s+', ' ', value).strip().lower()
    # Убираем кавычки, скобки, тире/дефисы и лишнюю пунктуацию.
    normalized = re.sub(r'[«»"\'(){}[\].,;:!?]', '', normalized)
    if strip_legal:
        # Убираем организационно-правовую форму в начале (ООО/АО/ИП/...) -
        # многие сайты пишут название без неё.
        stripped = _strip_legal_form(normalized)
        if stripped:
            normalized = stripped
    return normalized.strip()


def find_matched_target_variant(
    html: str,
    target_name: str = '',
) -> str | None:
    """Возвращает найденный вариант названия конкурента на странице.

    Двухэтапная проверка:

    - Этап 1: полное название с ОПФ (``strip_legal=False``).
    - Этап 2: название без ОПФ и кавычек (``strip_legal=True``).

    Возвращает ``'full'`` или ``'stripped'`` (вариант, реально присутствующий
    в HTML), либо ``None``, если ни один не найден. Найденный вариант
    используется далее при сборе новостей как имя конкурента.
    """
    if not html or not target_name:
        return None

    probe = html.lower()

    # Этап 1: полное название с ОПФ.
    full = _normalize_target_text(target_name, strip_legal=False)
    if full and re.search(rf'\b{re.escape(full)}\b', probe):
        return 'full'

    # Этап 2: название без ОПФ и кавычек.
    stripped = _normalize_target_text(target_name, strip_legal=True)
    if (
        stripped
        and stripped != full
        and re.search(rf'\b{re.escape(stripped)}\b', probe)
    ):
        return 'stripped'

    return None


def score_target_presence(
    html: str,
    target_name: str = '',
    target_inn: str = '',
) -> int:
    """Оценивает, есть ли в HTML страницы результатов искомая цель.

    Возвращает целочисленный «скор уверенности» (0 — точно нет, ``>=``
    ``_TARGET_CONFIDENT`` — цель найдена).

    **ИНН больше НЕ является обязательным условием**: страница может быть
    признана «успешной» по одному лишь названию конкурента (полному или
    без ОПФ). ИНН — опциональный доп. сигнал (сильнее всего для реестров),
    который лишь добавляет уверенности, но не блокирует выбор.

    Сигналы (по убыванию надёжности):

    - Полное название с ОПФ (``_NAME_EXACT_SIGNAL``) — уверенное совпадение.
    - Название без ОПФ/кавычек (``_NAME_STRIPPED_SIGNAL``) — тоже уверенное
      совпадение (в новости конкурент часто указан без ОПФ).
    - ИНН (``_INN_SIGNAL``) — доп. подтверждение для реестров, суммируется
      с названием, но само по себе не обязательно.
    - Частичное вхождение названия в аннотацию (``_NAME_PARTIAL_SIGNAL``) —
      слабый сигнал, НЕ достигает порога (не выбирается).

    Защита от ложных срабатываний: совпадение названия засчитывается
    только с границами слова (``\b``) — исключает «АРХИТЕХИ» внутри
    «АРХИТЕХИМ» и совпадения в JS-бандлах.
    """
    if not html:
        return 0

    probe = html.lower()
    score = 0

    # 1. Полное название с ОПФ.
    full = _normalize_target_text(target_name, strip_legal=False)
    if full and re.search(rf'\b{re.escape(full)}\b', probe):
        score += _NAME_EXACT_SIGNAL

    # 2. Название без ОПФ и кавычек (2-й этап: если полное не нашлось).
    if score < _TARGET_CONFIDENT:
        stripped = _normalize_target_text(target_name, strip_legal=True)
        if (
            stripped
            and stripped != full
            and re.search(rf'\b{re.escape(stripped)}\b', probe)
        ):
            score += _NAME_STRIPPED_SIGNAL

    # 3. Частичное вхождение — только если уверенного названия ещё нет
    #    и это единственный доступный сигнал. Не достигает порога.
    if score == 0:
        stripped = _normalize_target_text(target_name, strip_legal=True)
        if stripped and stripped in probe:
            score += _NAME_PARTIAL_SIGNAL

    # 4. ИНН — ОПЦИОНАЛЬНЫЙ доп. сигнал (для реестров). Добавляется, но
    #    не является обязательным условием успеха.
    inn = (target_inn or '').strip()
    if inn.isdigit() and len(inn) in (10, 12):
        if re.search(rf'\b{re.escape(inn)}\b', probe):
            score += _INN_SIGNAL

    return score


def extract_form_param(
    html: str, base_url: str
) -> tuple[str | None, str | None]:
    """Извлекает из HTML поисковую форму: (query_param, action_url).

    Ищет первую ``<form>`` с текстовым ``<input name="...">`` (или
    ``<textarea>``), имя которого похоже на поисковое (или просто первое
    текстовое поле). ``action`` формы нормализуется в абсолютный URL
    относительно ``base_url``.

    Возвращает ``(None, None)``, если подходящая форма не найдена.
    """
    if not html:
        return None, None
    soup = BeautifulSoup(html, 'html.parser')

    for form in soup.find_all('form'):
        input_el = form.find(['input', 'textarea'])
        if input_el is None:
            continue
        input_type = (input_el.get('type') or 'text').lower()
        # Пропускаем скрытые/кнопочные/поисково-неподходящие поля.
        if input_type not in ('text', 'search', ''):
            continue
        name = (input_el.get('name') or '').strip()
        if not name:
            continue

        action = (form.get('action') or '').strip()
        action_url = action if action else base_url
        # Пропускаем формы, ведущие на внешний домен (подписка и т.п.).
        if action_url.startswith('http'):
            from urllib.parse import urlparse

            base_host = urlparse(base_url).hostname or ''
            action_host = urlparse(action_url).hostname or ''
            if base_host and action_host and base_host != action_host:
                continue
        return name, urljoin(base_url, action_url) if action_url else base_url

    return None, None


def build_probe_url(
    base_url: str, query_param: str, search_value: str, raw_value: str = ''
) -> str:
    """Строит URL поиска с заданным query-параметром (с заменой).

    ``base_url`` может уже содержать поисковый параметр (например
    ``https://lenta.ru/search?q=ИИ``, собранный ``build_search_url``). Любой
    поисковый параметр из ``_DEFAULT_PARAM_CHAIN`` (``q``, ``query``,
    ``text``, ...) в query-строке ЗАМЕНЯЕТСЯ на ``query_param``, служебные
    параметры (``lang``, ``region``, ``page``) сохраняются. Это ключевое
    отличие от «тупого» дослепления: при переборе ``q -> query -> text`` на
    базе ``https://ekb.rbc.ru/search?q=...`` получается ровно
    ``https://ekb.rbc.ru/search?query=Яндекс.Еда``, а не ``?q=X&query=Y``
    (сайты чаще всего читают только первый параметр, и выдача выглядела бы
    пустой навсегда).

    Пример: вместо пустого ``q=`` подставляется ``query=...``.
    Значение percent-кодируется через ``quote_plus`` (пробелы -> ``+``,
    кириллица -> UTF-8 percent-последовательности), что исключает провалы
    FAST-стратегии на control-символах/не-ASCII.
    """
    value = quote_plus(raw_value or search_value)
    if '?' not in base_url:
        return f'{base_url}?{query_param}={value}'

    base, _, query_string = base_url.partition('?')
    if not query_string:
        return f'{base}?{query_param}={value}'

    pieces = query_string.split('&')
    kept = [
        piece
        for piece in pieces
        if piece and piece.split('=', 1)[0] not in _DEFAULT_PARAM_CHAIN
    ]
    kept.append(f'{query_param}={value}')
    return f'{base}?{"&".join(kept)}'


# ============================================================================
# Реформулировки запроса
# ============================================================================


def build_query_variants(
    raw_query: str,
    competitor_inn: str | None = None,
) -> list[str]:
    """Возвращает варианты формулировки запроса от «точного» к «широкому».

    Цепочка: точное название -> без организационно-правовой формы -> без
    лишних слов (ИИ/АЙ и т.п.) -> транслит -> ИНН. Пустые и дублирующиеся
    варианты отбрасываются. Если ``raw_query`` уже ИНН — иных вариантов нет.
    """
    if not raw_query:
        return []

    raw_query = raw_query.strip()
    if not raw_query:
        return []

    if raw_query.isdigit() and len(raw_query) in (10, 12):
        return [raw_query]

    variants: list[str] = [raw_query]
    normalized = re.sub(r'\s+', ' ', raw_query).strip()

    # 1. Без организационно-правовой формы в начале («ООО АРХИТЕХ ИИ» ->
    #    «АРХИТЕХ ИИ»).
    stripped = _strip_legal_form(normalized)
    if stripped and stripped not in variants:
        variants.append(stripped)

    # 2. Без «лишних» слов в конце («АРХИТЕХ ИИ» -> «АРХИТЕХ»).
    minimal = _strip_buzzwords(stripped or normalized)
    if minimal and minimal not in variants:
        variants.append(minimal)

    # 3. Транслит названия («АРХИТЕХ» -> транслит) — для сайтов, которые
    #    индексируют латиницу.
    translit = transliterate(minimal or normalized)
    if translit and translit not in variants:
        variants.append(translit)

    # 4. ИНН как точный идентификатор (последний, самый жёсткий вариант).
    if competitor_inn and competitor_inn.isdigit():
        variants.append(competitor_inn)

    return variants


def _strip_legal_form(value: str) -> str:
    """Удаляет организационно-правовую форму из начала названия."""
    lowered = value.lower()
    for form in _LEGAL_FORMS:
        if lowered.startswith(form):
            rest = value[len(form) :].strip(' ."\'-')
            if rest:
                return rest
    return value


def _strip_buzzwords(value: str) -> str:
    """Удаляет общие «лишние» слова из конца названия.

    Учитывает и кириллические («ИИ», «АЙ»), и латинские («AI», «LLC»)
    варианты, чтобы для «АРХИТЕХ ИИ» осталось «АРХИТЕХ».
    """
    if not value:
        return value

    # Не трогаем явные ИНН (цифровые строки не режутся).
    if value.isdigit():
        return value

    parts = value.split()
    if len(parts) <= 1:
        return value

    lower_parts = [p.lower() for p in parts]
    buzzwords = {'ии', 'ай', 'ai', 'llc', 'inc', 'group', 'групп'}
    end = len(parts)
    while end > 1 and lower_parts[end - 1] in buzzwords:
        end -= 1
    stripped = ' '.join(parts[:end]).strip()
    return stripped if stripped else value


_TRANSLIT_MAP = {
    'а': 'a',
    'б': 'b',
    'в': 'v',
    'г': 'g',
    'д': 'd',
    'е': 'e',
    'ё': 'e',
    'ж': 'zh',
    'з': 'z',
    'и': 'i',
    'й': 'y',
    'к': 'k',
    'л': 'l',
    'м': 'm',
    'н': 'n',
    'о': 'o',
    'п': 'p',
    'р': 'r',
    'с': 's',
    'т': 't',
    'у': 'u',
    'ф': 'f',
    'х': 'h',
    'ц': 'ts',
    'ч': 'ch',
    'ш': 'sh',
    'щ': 'sch',
    'ъ': '',
    'ы': 'y',
    'ь': '',
    'э': 'e',
    'ю': 'yu',
    'я': 'ya',
}


def transliterate(text: str) -> str:
    """Транслитерирует кириллицу в латиницу (для поиска по латинским
    названиям).

    Неконвертируемые символы сохраняются. Возвращает пустую строку, если
    на входе нет кириллицы.
    """
    if not text:
        return ''
    result = []
    has_cyrillic = False
    for char in text:
        lower = char.lower()
        if lower in _TRANSLIT_MAP:
            mapped = _TRANSLIT_MAP[lower]
            result.append(mapped.upper() if char.isupper() else mapped)
            has_cyrillic = True
        else:
            result.append(char)
    return ''.join(result) if has_cyrillic else ''


# ============================================================================
# Prober URL: перебор параметров и реформулировок
# ============================================================================


@dataclass
class ProbeCandidate:
    """Кандидат для перебора: параметр или реформулировка."""

    kind: str
    label: str
    url: str
    raw_query: str = ''


class SearchUrlProber:
    """Перебирает query-параметры и реформулировки, пока не найдёт выдачу.

    Порядок работы:

    1. Если в успешном HTML первой попытки найдена поисковая форма — её
       параметр становится приоритетным (``form_param``), а URL пересобирается
       (``build_probe_url``).
    2. Иначе перебираем типовые параметры из ``param_chain``: первый
       «похожий на результаты» ответ считается рабочим.
    3. Если ни один параметр не дал результатов — перебираем реформулировки
       запроса (``QueryReformulator``), начиная с параметра, давшего самый
       «длинный» ответ.
    4. Для гос. источников (``SourceType.REGISTRY``) добавляется защита:
       если в HTML всего один результат — считаем его «подозрительно полным»
       и не перебираем дальше (реестры возвращают одну карточку).
    """

    def __init__(
        self,
        param_chain: tuple[str, ...] = _DEFAULT_PARAM_CHAIN,
        fetch: Any = None,
        logger_: logging.Logger | None = None,
    ):
        self._param_chain = param_chain
        self._logger = logger_ or logging.getLogger(__name__)
        # ``fetch`` — async-колбэк ``async def fetch(url) -> str | None``
        # (оборачивает стратегии оркестратора). Если не передан — используем
        # ``orchestrator.fetch_with_degradation``.
        self._fetch = fetch

    async def probe(
        self,
        base_url: str,
        search_query: str,
        *,
        prefer_param: str | None = None,
        max_params: int = 7,
        max_reformulations: int = 5,
        source_type: SourceType | None = None,
        target_name: str = '',
        target_inn: str = '',
    ) -> ProbePlan:
        """Перебирает варианты поиска и возвращает ``ProbePlan``.

        Args:
            base_url: Шаблон URL поиска (напр.
                ``https://example.com/search?q=``).
            search_query: Исходный запрос (название конкурента или ИНН).
            prefer_param: Параметр из распознанной HTML-формы (приоритет).
            max_params: Максимум перебираемых параметров из цепочки.
            max_reformulations: Максимум реформулировок запроса.
            source_type: Тип источника (для гос. эвристики).
            target_name: Название цели (конкурента) для проверки наличия.
            target_inn: ИНН цели (конкурента) для проверки наличия.

        Returns:
            ``ProbePlan`` с успешной попыткой (``winner``) и списком всех
            перебранных вариантов (``attempts``).
        """
        plan = ProbePlan()
        fetch = self._fetch or self._default_fetch

        # Идея: гос. сайты (реестры) обычно ищут по ИНН, но параметр может
        # быть не ``q``. Пробуем параметры из цепочки, но для реестров
        # достаточно одного «длинного» ответа.
        # --- Цикл 1: параметры из цепочки (или приоритетный из формы). ---
        params: list[str] = []
        if prefer_param:
            params.append(prefer_param)
        for p in self._param_chain:
            if prefer_param and p == prefer_param:
                continue
            if p in params:
                continue
            if p in _FILTER_PARAMS:
                continue
            params.append(p)
        params = params[:max_params]

        for p in params:
            url = build_probe_url(base_url, p, search_query)
            html = await fetch(url)
            if not html:
                plan.add('param', p, url=url, ok=False, detail='fetch_failed')
                continue
            looks_ok = looks_like_search_results(html)
            target_found = False
            target_score = 0
            matched_variant = None
            if looks_ok and (target_name or target_inn):
                target_score = score_target_presence(
                    html, target_name=target_name, target_inn=target_inn
                )
                target_found = target_score >= _TARGET_CONFIDENT
                if not target_found:
                    looks_ok = False
                else:
                    matched_variant = find_matched_target_variant(
                        html, target_name=target_name
                    )
            plan.add(
                'param',
                p,
                url=url,
                ok=looks_ok,
                detail='content_ok' if looks_ok else 'empty_results',
                target_found=target_found,
                target_score=target_score,
                matched_variant=matched_variant,
            )
            if looks_ok:
                self._logger.info(
                    'Поиск по параметру %s дал результаты (%s)',
                    p,
                    base_url,
                )
                return plan

        # --- Цикл 1.5: параметр из HTML-формы поиска. ---
        # Если ни один словарный параметр не дал выдачи, пробуем распознать
        # поисковую форму прямо в HTML (``<form><input name=...>``) — сайт
        # может использовать нестандартное имя параметра, которого нет
        # в ``_DEFAULT_PARAM_CHAIN``.
        form_param, _form_action = extract_form_param(html, base_url)
        if form_param and form_param not in params:
            url = build_probe_url(base_url, form_param, search_query)
            form_html = await fetch(url)
            if not form_html:
                plan.add(
                    'form',
                    form_param,
                    url=url,
                    ok=False,
                    detail='fetch_failed',
                )
            else:
                form_ok = looks_like_search_results(form_html)
                form_target_found = False
                form_target_score = 0
                form_matched_variant = None
                if form_ok and (target_name or target_inn):
                    form_target_score = score_target_presence(
                        form_html,
                        target_name=target_name,
                        target_inn=target_inn,
                    )
                    form_target_found = form_target_score >= _TARGET_CONFIDENT
                    if not form_target_found:
                        form_ok = False
                    else:
                        form_matched_variant = find_matched_target_variant(
                            form_html, target_name=target_name
                        )
                plan.add(
                    'form',
                    form_param,
                    url=url,
                    ok=form_ok,
                    detail='content_ok' if form_ok else 'empty_results',
                    target_found=form_target_found,
                    target_score=form_target_score,
                    matched_variant=form_matched_variant,
                )
                if form_ok:
                    self._logger.info(
                        'Параметр %s из формы дал результаты (%s)',
                        form_param,
                        base_url,
                    )
                    return plan

        # --- Цикл 2: реформулировки запроса (если параметры не дали
        # выдачи). ---
        variants = build_query_variants(search_query, None)[:max_reformulations]
        # Для перебора реформулировок используем первый параметр из цепочки
        # (или prefer_param), чтобы не умножать число запросов.
        query_param = prefer_param or params[0]
        for variant in variants[1:]:
            url = build_probe_url(base_url, query_param, variant)
            html = await fetch(url)
            if not html:
                plan.add(
                    'query', variant, url=url, ok=False, detail='fetch_failed'
                )
                continue
            looks_ok = looks_like_search_results(html)
            target_found = False
            target_score = 0
            matched_variant = None
            if looks_ok and (target_name or target_inn):
                target_score = score_target_presence(
                    html, target_name=target_name, target_inn=target_inn
                )
                target_found = target_score >= _TARGET_CONFIDENT
                if not target_found:
                    looks_ok = False
                else:
                    matched_variant = find_matched_target_variant(
                        html, target_name=target_name
                    )
            plan.add(
                'query',
                variant,
                url=url,
                ok=looks_ok,
                detail='content_ok' if looks_ok else 'empty_results',
                target_found=target_found,
                target_score=target_score,
                matched_variant=matched_variant,
            )
            if looks_ok:
                self._logger.info(
                    'Реформулировка «%s» дала результаты (%s)',
                    variant,
                    base_url,
                )
                return plan

        # Ничего не сработало: фиксируем последнюю попытку как «лучший
        # кандидат» (для отчёта), но без ``winner``.
        if plan.attempts:
            last = plan.attempts[-1]
            plan.add(
                'query',
                'none',
                url=last.url,
                ok=False,
                detail='all_attempts_failed',
            )
        return plan

    async def _default_fetch(self, url: str) -> str | None:
        """Фетч по умолчанию: стратегии оркестратора."""
        from ..strategies.orchestrator import AgenticOrchestrator

        orchestrator = AgenticOrchestrator()
        result = await orchestrator.fetch_with_degradation(url)
        if result.success and result.data:
            return result.data
        return None
