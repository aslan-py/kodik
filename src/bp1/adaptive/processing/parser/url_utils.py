"""Работа с URL: фильтрация служебных/рекламных ссылок, нормализация."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# Служебные пути URL, которые не являются элементами данных и должны быть
# отброшены при извлечении (логин, регистрация, cookie-политика и т.п.).
# Проверяются по подстроке пути — работают независимо от того, в каком теге
# живёт ссылка на странице (nav, div, span и т.д.).
_NOISE_URL_PATTERNS: tuple[str, ...] = (
    '/account/',
    '/login',
    '/signup',
    '/register',
    '/logout',
    '/recover',
    '/reset',
    '/article/cookie_policy',
    '/cookie_policy',
    '/privacy',
    '/favicon',
)


def _is_noise_url(url: str) -> bool:
    """Возвращает True, если URL является служебным и его нужно отбросить.

    Проверяет по подстроке пути из ``_NOISE_URL_PATTERNS``. Логин, cookie-
    политика и подобные служебные ссылки не являются элементами данных: они
    дублируются на странице и порождают ложные ``duplicate key`` на уровне
    CONSISTENCY-карантина.

    Не отбрасываются: пустые/корневые ссылки и обычные навигационные пункты
    (например ``/#forburger`` или ``mailto:``) — они не служебные и должны
    сохраняться.
    """
    if not url or not isinstance(url, str):
        return False

    path = url.split('?', 1)[0].split('#', 1)[0]
    if any(pattern in path for pattern in _NOISE_URL_PATTERNS):
        return True
    # Служебные ссылки ограничены шаблонами выше. Не-HTTP(S) ссылки
    # (``mailto:``, ``tel:``, ``javascript:``) не считаются шумом здесь:
    # их отфильтровывает ``_is_fetchable_url`` на уровне кандидатов.
    return False


def _is_ad_redirect_url(url: str) -> bool:
    """Возвращает True для рекламных редирект-ссылок (клик-трекеров).

    hh.ru отдаёт спонсированные вакансии через отдельный поддомен
    ``adsrv.hh.ru/click?...`` — визуально это ссылка на вакансию, но
    deep-fetch такого URL скачивает страницу рекламной системы (редирект),
    а не саму вакансию, из-за чего каскад извлечения текста либо не находит
    ничего, либо извлекает контент, не относящийся к запросу. Узкая,
    специфичная для hh.ru-подобных доменов эвристика — при появлении
    похожих паттернов на других источниках (``/redirect?``, ``/away.php``,
    сторонние рекламные домены) расширить тем же способом.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host.startswith('adsrv.')


def _reject_non_http_scheme(url: str) -> bool:
    """Возвращает True для явных не-HTTP(S) схем
    (``mailto:``, ``tel:``, ``javascript:``).

    Относительные ссылки (без ``:``) и обычные URL пропускаются — они
    нормализуются в абсолютные через ``_to_absolute``.
    """
    if not url or not isinstance(url, str):
        return False
    if ':' not in url:
        return False
    scheme = url.split(':', 1)[0].lower()
    return scheme not in ('http', 'https')


def _to_absolute(url: str, base_url: str) -> str:
    """Превращает относительный путь в полный абсолютный URL.

    Схема/домен берутся из ``base_url`` (URL страницы результата поиска).
    Уже абсолютные ссылки (``http://``, ``https://``, ``mailto:``) возвращаются
    без изменений, чтобы не ломать другие типы ссылок.

    Args:
        url: Ссылка, извлечённая из заголовка новости (может быть
            относительной, например ``/about/news/...``).
        base_url: Базовый URL страницы, на которой найдена ссылка.

    Returns:
        Полный абсолютный URL.
    """
    if not url or not isinstance(url, str):
        return ''
    if '://' in url:
        return url
    return urljoin(base_url, url)


def _is_fetchable_url(url: str) -> bool:
    """Возвращает True, если по URL можно выполнить HTTP-запрос.

    Отфильтровывает ``mailto:``, ``tel:``, ``javascript:`` и прочие схемы, не
    являющиеся ``http``/``https``. Такие ссылки не скачиваются стратегиями
    обхода (FAST/CRAWL4AI/BROWSER падают на них с ошибкой URL scheme), поэтому
    на уровне глубокого фетча они пропускаются, а элемент остаётся со
    сниппетом-заголовком.
    """
    if not url or not isinstance(url, str):
        return False
    scheme = url.split(':', 1)[0].lower()
    return scheme in ('http', 'https')


class _LinkCollector(HTMLParser):
    """Собирает ссылки и заголовки из HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_text: list[str] = []
        self._in_a = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        if tag == 'a':
            self._in_a = True
            self._current_text = []
            href = dict(attrs).get('href')
            if href:
                self._pending_href = href

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self._in_a:
            self._in_a = False
            text = ' '.join(self._current_text).strip()
            href = getattr(self, '_pending_href', '')
            # Относительные ссылки (без ``:``) сохраняются — они станут
            # абсолютными через ``_to_absolute``. Не-HTTP(S) схемы
            # (``mailto:``, ``tel:``, ``javascript:``) в парсинг не попадают.
            if text and href and not _reject_non_http_scheme(href):
                self.links.append((text, href))
