"""Извлечение элементов по CSS-селекторам через BeautifulSoup."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


def _node_field_value(field: str, node: Any) -> str:
    """Достаёт значение поля из узла (href/src для url, иначе текст)."""
    if field == 'url':
        href = node.get('href') or node.get('src') or ''
        return str(href).strip()
    return node.get_text(' ', strip=True)


def _single_item_from_matches(
    field_matches: dict[str, list[Any]],
) -> dict[str, str]:
    """Собирает один элемент — по одному (первому) совпадению на поле."""
    item: dict[str, str] = {}
    for field, nodes in field_matches.items():
        if not nodes:
            continue
        value = _node_field_value(field, nodes[0])
        if value:
            item[field] = value
    return item


def _multi_items_from_matches(
    field_matches: dict[str, list[Any]], max_matches: int
) -> list[dict[str, str]]:
    """Раскладывает совпадения по индексу — контейнер оказался списком
    записей: i-е совпадение title соответствует i-му url и т.д.
    (стандартный паттерн: поля одной карточки идут в одном и том же
    порядке в DOM для каждой карточки).
    """
    items: list[dict[str, str]] = []
    for i in range(max_matches):
        item: dict[str, str] = {}
        for field, nodes in field_matches.items():
            if i >= len(nodes):
                continue
            value = _node_field_value(field, nodes[i])
            if value:
                item[field] = value
        if item:
            items.append(item)
    return items


def _extract_by_selectors(
    html: str, selectors: dict[str, str]
) -> list[dict[str, str]]:
    """Извлекает элементы по CSS-селекторам через BeautifulSoup.

    Для каждого контейнера (``selectors['container']``) извлекает поля
    (title, text, url, published_at, region, media_name) по соответствующим
    селекторам. Корректно обрабатывает вложенные контейнеры.

    LLM-анализ структуры иногда путает "контейнер одной записи" (карточка)
    с "контейнером списка" (обёртка вокруг ВСЕХ карточек, например
    ``ol.vacancies-list``/``ul.search-results__list``) — тогда
    ``container_selector`` матчит единственный элемент на всю страницу.
    Если внутри такого контейнера селектор поля (например ``title``/``url``)
    находит НЕСКОЛЬКО совпадений вместо одного — это и есть признак
    контейнера-списка: результат "разворачивается" в несколько записей по
    индексу совпадения, а не схлопывается в одну (что раньше происходило
    из-за ``container.select_one(...)``, бравшего только первое совпадение
    на всю страницу — вместо 10 новостей/вакансий оставалась 1).

    Args:
        html: Исходный HTML.
        selectors: Словарь ``{поле: css-селектор}``, где ``container`` —
            селектор контейнера элемента.

    Returns:
        Список извлечённых элементов (словарей с полями).
    """
    container_selector = (selectors.get('container') or '').strip()
    if not container_selector:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    containers = soup.select(container_selector)
    items: list[dict[str, str]] = []

    field_selectors = {
        field: selector
        for field, selector in selectors.items()
        if field != 'container' and selector
    }

    for container in containers:
        field_matches = {
            field: container.select(selector)
            for field, selector in field_selectors.items()
        }
        match_lengths = (len(nodes) for nodes in field_matches.values())
        max_matches = max(match_lengths, default=0)

        if max_matches <= 1:
            # Обычный случай: контейнер — одна запись, у каждого поля не
            # больше одного совпадения внутри неё.
            item = _single_item_from_matches(field_matches)
            if item:
                items.append(item)
        else:
            # Контейнер оказался списком записей.
            items.extend(_multi_items_from_matches(field_matches, max_matches))

    return items
