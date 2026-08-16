"""Пагинация страниц выдачи и сборка элементов данных из HTML."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from . import constants
from .selectors import _extract_by_selectors
from .url_utils import (
    _is_ad_redirect_url,
    _is_noise_url,
    _LinkCollector,
    _reject_non_http_scheme,
    _to_absolute,
)


def _items_per_page(selectors: dict[str, str] | None) -> int:
    """Число элементов на странице выдачи из метаданных адаптера.

    LLM-анализ структуры возвращает ``items_per_page`` в ``metadata``
    (см. ``_ANALYSIS_RESPONSE_RULES``); значение попадает в селекторы
    адаптера. Используется для выбора стиля пагинации
    (``_pagination_url``) и для сужения лимита страниц (``_max_pages``).

    Returns:
        Положительное число элементов или 0, если значение не задано или
        не приводится к целому.
    """
    raw = (selectors or {}).get('items_per_page')
    try:
        value = int(raw) if raw else 0
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _pagination_url(
    base_url: str,
    page: int,
    items_per_page: int = 0,
) -> str:
    """Возвращает URL следующей страницы выдачи.

    Поддерживает два стиля пагинации (Шаг 16 плана рефакторинга,
    REFACTORING_PLAN.md):

    - **По номеру страницы** (по умолчанию): ``?page=N`` / ``&page=N``.
    - **По смещению** (``items_per_page > 0``): ``?offset=N`` — многие
      выдачи (особенно API-подобные и job-board) нумеруют не страницы, а
      элементы. Смещение считается как ``(page - 1) * items_per_page``.

    Стиль выбирается по ``items_per_page`` из ``metadata`` LLM-анализа
    (``_ANALYSIS_RESPONSE_RULES`` просит модель его вернуть): если размер
    страницы известен, значит выдача сама сообщила о постраничной
    структуре, и смещение вычислимо; иначе остаётся ``page=N``.

    Args:
        base_url: URL первой страницы результата поиска.
        page: Номер страницы (1 — первая, без параметра пагинации).
        items_per_page: Число элементов на странице (0 — неизвестно).

    Returns:
        URL страницы пагинации.
    """
    if page <= 1:
        return base_url
    sep = '&' if '?' in base_url else '?'
    if items_per_page > 0:
        return f'{base_url}{sep}offset={(page - 1) * items_per_page}'
    return f'{base_url}{sep}page={page}'


def _page_items(
    html: str,
    source_name: str,
    competitor: str,
    trigger: str,
    selectors: dict[str, str],
    base_url: str,
) -> list[tuple[str, str, str]]:
    """Извлекает пары ``(title, url_abs, url_rel)`` из страницы результатов.

    Использует селектор ``container``/``url``/``title`` адаптера, если задан,
    иначе — эвристический сбор ссылок. ``url_abs`` — полный абсолютный URL.
    """
    selectors = selectors or {}
    pairs: list[tuple[str, str]] = []

    # Если задан контейнер, извлекаем элементы по селекторам полей адаптера.
    # Если контейнер есть, но у него нет рабочих селекторов ``url``/``title``
    # (LLM вернул только ``container``, а остальные поля пустые) — по
    # ``_extract_by_selectors`` мы не сможем собрать ни одного элемента
    # (url/title пустые → все отбрасываются). Тогда деградируем к
    # эвристическому сбору ссылок внутри контейнера, чтобы не терять выдачу.
    has_container = bool((selectors.get('container') or '').strip())
    has_field_selectors = bool(selectors.get('url') and selectors.get('title'))

    if has_container and has_field_selectors:
        for raw in _extract_by_selectors(html, selectors):
            url_rel = raw.get('url', '')
            title = raw.get('title', '')
            if (
                _is_noise_url(url_rel)
                or _is_ad_redirect_url(url_rel)
                or _reject_non_http_scheme(url_rel)
                or not title
            ):
                continue
            pairs.append((title, url_rel))
            if len(pairs) >= constants.DEFAULT_MAX_NEWS:
                break
    else:
        # Эвристический сбор ссылок. Если контейнер задан, ограничиваем сбор
        # его областью (иначе соберутся навигационные ссылки шапки/подвала).
        # select() — ВСЕ совпадения (карточки), а не только первая: раньше
        # select_one() брал первую карточку из N на странице листинга, и
        # _LinkCollector видел ссылки только внутри неё — отсюда терялись
        # почти все новости (например, 1 из 10 на lenta.ru).
        if has_container:
            soup = BeautifulSoup(html, 'html.parser')
            containers = soup.select(selectors['container'])
            container_html = (
                ''.join(str(c) for c in containers) if containers else html
            )
        else:
            container_html = html
        collector = _LinkCollector()
        collector.feed(container_html)
        for title, href in collector.links:
            if (
                _is_noise_url(href)
                or _is_ad_redirect_url(href)
                or _reject_non_http_scheme(href)
            ):
                continue
            pairs.append((title, href))
            if len(pairs) >= constants.DEFAULT_MAX_NEWS:
                break

    return [
        (title, _to_absolute(url_rel, base_url), url_rel)
        for title, url_rel in pairs
    ]


def _make_search_page_item(
    source_name: str,
    url: str,
    title: str,
) -> dict[str, Any]:
    """Формирует элемент для самой страницы результата поиска.

    Первая страница — это страница поиска, а не первая новость. Поэтому
    ``url`` = страница поиска (с поисковым запросом), ``title`` = собственный
    ``<title>`` этой страницы. Найденные новости попадают в ``extra.news``
    (поля ex_title/ex_url/ex_text), т.е. ``items.title`` НЕ равен
    ``extra.news[].ex_title`` — это разные страницы.
    """
    return {
        'url': url,
        'title': title,
        'text': None,
        'published_at': None,
        'region': None,
        'media_name': source_name,
        'extra': {},
    }


def _make_item(
    source_name: str,
    competitor: str,
    trigger: str,
    url: str,
    title: str,
    text: str | None = None,
    published_at: str | None = None,
    region: str | None = None,
    media_name: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Формирует элемент данных из извлечённых полей.

    ``competitor``/``trigger`` НЕ попадают в ``extra`` — это поля уровня
    ``meta`` (переносятся в ParsedResponse.meta в bridge.py). URL нормализуется
    до полного абсолютного (``base_url`` = URL страницы результата поиска),
    т.к. относительные ссылки ломают dedup_key и media_domain в BP-2.
    """
    return {
        'url': _to_absolute(url, base_url or ''),
        'title': title,
        'text': text,
        'published_at': published_at,
        'region': region,
        'media_name': media_name or source_name,
        'extra': {},
    }


def _parse_items(
    html: str,
    source_name: str,
    competitor: str,
    trigger: str,
    selectors: dict[str, str] | None = None,
    base_url: str | None = None,
) -> list[dict[str, Any]]:
    """
    Извлекает элементы из HTML.

    Если задан селектор ``container`` — извлекает элементы по селекторам
    адаптера (title, text, url, published_at, region) через BeautifulSoup.
    Иначе использует эвристический парсер ссылок: каждая ссылка с текстом
    становится кандидатом в элемент. ``base_url`` (URL страницы результата
    поиска) используется для нормализации относительных ссылок в полные.
    """
    selectors = selectors or {}

    if selectors.get('container'):
        items: list[dict[str, Any]] = []
        for raw in _extract_by_selectors(html, selectors):
            if (
                _is_noise_url(raw.get('url'))
                or _is_ad_redirect_url(raw.get('url'))
                or _reject_non_http_scheme(raw.get('url'))
            ):
                continue
            items.append(
                _make_item(
                    source_name=source_name,
                    competitor=competitor,
                    trigger=trigger,
                    url=raw.get('url', ''),
                    title=raw.get('title', ''),
                    text=raw.get('text'),
                    published_at=raw.get('published_at'),
                    region=raw.get('region'),
                    media_name=raw.get('media_name'),
                    base_url=base_url,
                )
            )
            if len(items) >= constants.DEFAULT_MAX_NEWS:
                break
        return items

    collector = _LinkCollector()
    collector.feed(html)

    items = []
    for title, href in collector.links:
        if (
            _is_noise_url(href)
            or _is_ad_redirect_url(href)
            or _reject_non_http_scheme(href)
        ):
            continue
        items.append(
            _make_item(
                source_name=source_name,
                competitor=competitor,
                trigger=trigger,
                url=href,
                title=title,
                base_url=base_url,
            )
        )
        if len(items) >= constants.DEFAULT_MAX_NEWS:
            break
    return items
