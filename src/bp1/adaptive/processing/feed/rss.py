"""RSS/Atom -> материалы сбора (BP-1 Adaptive, RSS/sitemap).

Прямое сопоставление полей записи ``feedparser`` в форму, которую уже
производит ``_deep_fetch`` (``ex_title``/``ex_url``/``ex_text``/
``ex_method``/...) — без LLM и без CSS-селекторов (design.md D2).
"""

from __future__ import annotations

from typing import Any

import feedparser


def parse_rss_entries(raw_body: str) -> list[Any]:
    """Разбирает RSS/Atom через ``feedparser``.

    ``feedparser`` устойчив к невалидному/нестрогому XML — при ошибке
    разбора выставляет ``bozo=1``, но всё равно пытается вернуть то, что
    смог распознать. Пустой список записей (валидный XML без записей ИЛИ
    невалидный XML, из которого ничего не извлеклось) — оба случая для
    вызывающего кода означают одно и то же: использовать нечего.

    Returns:
        Список записей ``feedparser`` (пустой, если фид невалиден/пуст).
    """
    parsed = feedparser.parse(raw_body or '')
    return list(parsed.entries)


def entries_to_materials(entries: list[Any]) -> list[dict[str, Any]]:
    """Сопоставляет записи ``feedparser`` в форму материалов сбора.

    Запись без ссылки или без заголовка пропускается — оба поля обязательны
    для последующей конвертации в ``ParsedItem`` (``bridge.py``).

    Returns:
        Список словарей ``ex_title``/``ex_url``/``ex_text``/``ex_method``/
        ``ex_text_length``/``ex_text_possibly_incomplete`` — та же форма,
        что уже отдаёт ``AdaptiveParser._deep_fetch`` для HTML-пути.
    """
    materials: list[dict[str, Any]] = []
    for entry in entries:
        title = (getattr(entry, 'title', '') or '').strip()
        url = (getattr(entry, 'link', '') or '').strip()
        if not title or not url:
            continue
        text = (
            getattr(entry, 'summary', '')
            or getattr(entry, 'description', '')
            or ''
        ).strip()
        materials.append(
            {
                'ex_title': title,
                'ex_url': url,
                'ex_text': text or title,
                'ex_method': 'rss',
                'ex_text_length': len(text) if text else 0,
                'ex_text_possibly_incomplete': not bool(text),
            }
        )
    return materials
