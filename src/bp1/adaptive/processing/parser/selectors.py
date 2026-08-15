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


def _find_row_scope(
    anchor_node: Any, anchor_selector: str, container: Any
) -> Any:
    """Находит наименьшего предка ``anchor_node`` (в пределах ``container``),
    содержащего РОВНО одно совпадение ``anchor_selector`` — то есть не
    выходящего за границы одной записи списка. Если такого предка нет
    (плоская разметка без обёрток вокруг записи) — возвращает сам
    ``anchor_node``.
    """
    for ancestor in anchor_node.parents:
        if len(ancestor.select(anchor_selector)) == 1:
            return ancestor
        if ancestor is container:
            break
    return anchor_node


def _multi_items_from_matches(
    field_matches: dict[str, list[Any]],
    field_selectors: dict[str, str],
    container: Any,
) -> list[dict[str, str]]:
    """Раскладывает контейнер-список на отдельные записи.

    Не сопоставляет поля по голому индексу совпадения (``title[i]`` с
    ``url[i]``) — если у полей разное количество совпадений внутри
    контейнера (частый случай: ``url`` задан общим ``a[href]``, который
    матчит рекламу/работодателя/кнопку отклика внутри той же карточки, а
    не только саму запись — реальная разметка hh.ru даёт до 5-7 разных
    ``<a href>`` на одну вакансию), индексы расходятся и записи
    "разъезжаются" — заголовок одной вакансии приклеивается к ссылке
    совсем другого элемента.

    Вместо этого ``title`` (если задан, иначе первое доступное поле) —
    якорь: для каждого его совпадения находится наименьший охватывающий
    предок, изолирующий ровно одну запись (см. ``_find_row_scope``), и
    остальные поля ищутся уже внутри этого предка — то есть в границах
    именно этой карточки, а не всего контейнера-списка.
    """
    anchor_field = (
        'title'
        if field_selectors.get('title')
        else next(iter(field_selectors), None)
    )
    if anchor_field is None:
        return []
    anchor_nodes = field_matches.get(anchor_field) or []
    anchor_selector = field_selectors[anchor_field]

    items: list[dict[str, str]] = []
    for anchor_node in anchor_nodes:
        item: dict[str, str] = {}
        anchor_value = _node_field_value(anchor_field, anchor_node)
        if anchor_value:
            item[anchor_field] = anchor_value

        row = _find_row_scope(anchor_node, anchor_selector, container)
        for field, selector in field_selectors.items():
            if field == anchor_field:
                continue
            if (
                field == 'url'
                and getattr(anchor_node, 'name', None) == 'a'
                and anchor_node.get('href')
            ):
                # Якорный узел сам является ссылкой (типичный случай —
                # заголовок и есть ссылка на запись). Его собственный href
                # надёжнее независимого поиска ``url`` в границах карточки:
                # там может быть несколько разных <a href> (см. докстринг
                # выше), и select_one() взял бы первую по порядку в DOM, не
                # обязательно ту, что относится к заголовку.
                item['url'] = str(anchor_node.get('href')).strip()
                continue
            node = row.select_one(selector)
            if node is not None:
                value = _node_field_value(field, node)
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
            items.extend(
                _multi_items_from_matches(
                    field_matches, field_selectors, container
                )
            )

    return items
