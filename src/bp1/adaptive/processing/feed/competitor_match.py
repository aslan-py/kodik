"""Разметка материалов фида по совпадению с конкурентом, без LLM
(BP-1 Adaptive, RSS/sitemap, design.md D6).

Вопрос «встречается ли имя конкурента в тексте» не требует LLM — тот же
класс задачи, что BP-2 уже решает строковым совпадением (чёрные списки,
стоп-слова, ``dedup_key`` — ``ABOUT_PROJECT/ABOUT.md``). Нормализация —
тем же приёмом, что и ``dedup_key`` в BP-2: lowercase, без пунктуации,
схлопнутые пробелы.

Не фильтрует — только размечает полем ``relevance`` (1.0/0.0), тем же
именем поля, что уже использует LLM-based ``RelevanceFilter`` для
HTML-пути (``processing/relevance.py``), чтобы форма материала оставалась
единообразной независимо от источника данных.
"""

from __future__ import annotations

import re
from typing import Any

_PUNCTUATION_RE = re.compile(r'[^\w\s]', re.UNICODE)
_WHITESPACE_RE = re.compile(r'\s+')


def normalize_name(text: str) -> str:
    """lowercase, без пунктуации, схлопнутые пробелы (как ``dedup_key``
    в BP-2, ``ABOUT_PROJECT/ABOUT.md``)."""
    text = (text or '').lower()
    text = _PUNCTUATION_RE.sub('', text)
    return _WHITESPACE_RE.sub(' ', text).strip()


def matches_competitor(material: dict[str, Any], competitor: str) -> bool:
    """True, если нормализованное имя конкурента входит в
    заголовок+текст материала (точное вхождение, без алиасов/нечёткого
    сопоставления — ``Competitor`` не хранит алиасы, design.md
    Non-Goals)."""
    needle = normalize_name(competitor)
    if not needle:
        return False
    haystack = normalize_name(
        f'{material.get("ex_title", "")} {material.get("ex_text", "")}'
    )
    return needle in haystack


def annotate_materials(
    materials: list[dict[str, Any]], competitor: str
) -> list[dict[str, Any]]:
    """Размечает каждый материал полем ``relevance`` (1.0 — совпадение
    найдено, 0.0 — нет). Не фильтрует: материал без совпадения всё равно
    попадает в результат (specs/bp1/rss-sitemap-collection/spec.md,
    «Материалы из фида размечаются по совпадению с конкурентом»)."""
    annotated: list[dict[str, Any]] = []
    for material in materials:
        item = dict(material)
        item['relevance'] = 1.0 if matches_competitor(item, competitor) else 0.0
        annotated.append(item)
    return annotated
