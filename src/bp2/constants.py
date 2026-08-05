"""Константы предочистки текста для BP-2.

Вынесены из pipeline.py, чтобы не загромождать конвейер. Всё собрано в
классе TextCleanup — как атрибуты, чтобы импортировать одним именем и
обращаться через него (TextCleanup.CLEAN_TABLE, TextCleanup.HTML_TAG).
Используются в clean_text (см. src/bp2/pipeline.py).
"""

import re
from re import Pattern
from typing import ClassVar


class TextCleanup:
    """Готовые объекты для предочистки текста: таблица трансляции и регэкспы.

    Наружу нужны три атрибута — CLEAN_TABLE (для str.translate),
    HTML_SCRIPT_STYLE и HTML_TAG (для среза разметки). Остальное —
    промежуточные наборы кодпоинтов, из которых собирается таблица.
    """

    # Управляющие символы (0–31) — чистый мусор из кривого парсинга; \x00
    # вообще нельзя положить в text-колонку Postgres. Оставляем только \t \n
    # \r (легитимное форматирование, схлопнётся на последнем шаге).
    _CONTROL_CHARS: ClassVar[dict[int, str]] = {
        i: ''
        for i in range(128)
        if i not in (9, 10, 13) and (i < 32 or i == 127)
    }

    # Невидимые артефакты и «похожие на пробел» символы. Задаём КОДПОИНТАМИ,
    # а не литералами: иначе в исходнике оказались бы настоящие LS/PS
    # (U+2028/U+2029), которые редакторы считают переносами строк. Мягкий
    # перенос и zero-width семейство удаляем совсем (иначе «биле[shy]т» !=
    # «билет» в дедупе и стоп-словах); экзотические пробелы → обычный \x20.
    # Часть NFKC складывает сам, но держим таблицу явной — не на побочке.
    _ZERO_WIDTH: ClassVar[tuple[int, ...]] = (
        0x00AD,  # soft hyphen (мягкий перенос)
        0x200B,  # zero-width space (ZWSP)
        0x200C,  # zero-width non-joiner
        0x200D,  # zero-width joiner
        0x2060,  # word joiner
        0xFEFF,  # BOM / ZWNBSP
    )
    _SPACE_LOOKALIKES: ClassVar[tuple[int, ...]] = (
        0x00A0,  # неразрывный пробел (&nbsp;)
        0x202F,  # узкий неразрывный (narrow NBSP)
        0x2007,  # табличный пробел (figure space)
        0x2028,  # разделитель строк (LS)
        0x2029,  # разделитель абзацев (PS)
    )

    # Готовая таблица для str.translate: {кодпоинт: замена}.
    CLEAN_TABLE: ClassVar[dict[int, str | None]] = {
        **_CONTROL_CHARS,
        **dict.fromkeys(_ZERO_WIDTH, ''),
        **dict.fromkeys(_SPACE_LOOKALIKES, ' '),
    }

    # <script>/<style> вырезаем ВМЕСТЕ с содержимым (иначе после среза тегов
    # останется простыня JS/CSS как текст). DOTALL — код часто с переносами.
    HTML_SCRIPT_STYLE: ClassVar[Pattern[str]] = re.compile(
        r'<(script|style)[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL
    )
    # Остальные HTML-теги, притащенные кривым парсингом (<p>, <br>, <b>…).
    HTML_TAG: ClassVar[Pattern[str]] = re.compile(r'<[^>]+>')
