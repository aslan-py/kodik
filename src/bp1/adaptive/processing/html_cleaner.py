"""
HtmlCleaner — очистка и сжатие HTML перед LLM-анализом.

Удаляет шум (script, style, nav, footer, header, aside, noscript),
JavaScript-атрибуты, извлекает основной контент и метаданные. Сжимает
объём HTML в 2-3 раза, что критично для LLM с ограниченным контекстным
окном.

Использует BeautifulSoup (``bs4``) при наличии, иначе — упрощённый
fallback на основе ``html.parser`` из стандартной библиотеки.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - зависит от окружения
    from bs4 import BeautifulSoup

    _HAS_BS4 = True
except ImportError:  # pragma: no cover
    _HAS_BS4 = False

# Теги, которые не несут полезного контента для анализа структуры.
_NOISE_TAGS = {
    'script',
    'style',
    'nav',
    'footer',
    'header',
    'aside',
    'noscript',
    'iframe',
    'form',
    'svg',
    'canvas',
    'template',
}

# JavaScript-атрибуты, которые не нужны для анализа селекторов.
_JS_ATTRS = re.compile(r'^on\w+$')

# Теги, которые считаются контейнерами основного контента.
_CONTENT_TAGS = {'article', 'main', 'section', 'body'}


class HtmlCleaner:
    """Очищает HTML от шума и сжимает его до основного контента."""

    def __init__(
        self,
        min_text_length: int = 100,
        use_bs4: bool | None = None,
    ) -> None:
        """
        Args:
            min_text_length: Минимальная длина текста для сохранения блока.
            use_bs4: Принудительно использовать BeautifulSoup (или нет).
                По умолчанию — использовать, если он установлен.
        """
        self.min_text_length = min_text_length
        self._use_bs4 = _HAS_BS4 if use_bs4 is None else (use_bs4 and _HAS_BS4)

    def clean(
        self,
        html: str,
        extract_metadata: bool = True,
        min_text_length: int | None = None,
    ) -> dict[str, Any]:
        """
        Очищает HTML и возвращает структурированный контент.

        Args:
            html: Сырой HTML.
            extract_metadata: Извлекать ли метаданные (title, description).
            min_text_length: Минимальная длина текста для сохранения блока
                (переопределяет значение из конструктора).

        Returns:
            dict:
                - content: Очищенный HTML.
                - metadata: dict с title, description, keywords.
                - blocks: list[dict] — список логических блоков для
                  чанкирования.
                - stats: dict с количеством блоков, исходным и очищенным
                  размером.
        """
        min_len = min_text_length or self.min_text_length
        original_size = len(html)

        if self._use_bs4:
            cleaned, metadata, blocks = self._clean_with_bs4(
                html, extract_metadata, min_len
            )
        else:
            cleaned, metadata, blocks = self._clean_with_stdlib(
                html, extract_metadata, min_len
            )

        return {
            'content': cleaned,
            'metadata': metadata,
            'blocks': blocks,
            'stats': {
                'original_size': original_size,
                'cleaned_size': len(cleaned),
                'block_count': len(blocks),
                'compression_ratio': (
                    round(original_size / len(cleaned), 2) if cleaned else 0.0
                ),
            },
        }

    # ------------------------------------------------------------------
    # Реализация на BeautifulSoup
    # ------------------------------------------------------------------

    def _clean_with_bs4(
        self,
        html: str,
        extract_metadata: bool,
        min_len: int,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Очистка через BeautifulSoup."""
        soup = BeautifulSoup(html, 'html.parser')

        # 1. Удаление шумовых тегов.
        for tag in soup(_NOISE_TAGS):
            tag.decompose()

        # 2. Удаление JavaScript-атрибутов.
        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                if _JS_ATTRS.match(attr):
                    del tag.attrs[attr]

        # 3. Извлечение метаданных.
        metadata: dict[str, Any] = {}
        if extract_metadata:
            metadata = self._extract_metadata_bs4(soup)

        # 4. Извлечение основного контента.
        main = self._find_main_content_bs4(soup)

        # 5. Сбор логических блоков.
        blocks: list[dict[str, Any]] = []
        for block in main.find_all(['article', 'section', 'div', 'p']):
            text = block.get_text(' ', strip=True)
            if len(text) < min_len:
                continue
            blocks.append(
                {
                    'tag': block.name,
                    'text': text,
                    'html': str(block),
                    'classes': block.get('class', []),
                }
            )

        cleaned = str(main)
        return cleaned, metadata, blocks

    def _extract_metadata_bs4(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Извлекает title, description, keywords из BeautifulSoup."""
        metadata: dict[str, Any] = {}

        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            metadata['title'] = title_tag.string.strip()

        for meta in soup.find_all('meta'):
            name = (meta.get('name') or '').lower()
            prop = (meta.get('property') or '').lower()
            content = meta.get('content')
            if not content:
                continue
            if name == 'description' or prop == 'og:description':
                metadata['description'] = content
            elif name == 'keywords':
                metadata['keywords'] = content

        return metadata

    def _find_main_content_bs4(self, soup: BeautifulSoup) -> Any:
        """Находит основной контент страницы.

        Приоритет: body → main → article → section → весь документ.
        Возвращает самый внешний контейнер, чтобы не потерять вложенные
        блоки (например, несколько article внутри body).
        """
        for tag in ('body', 'main', 'article', 'section'):
            found = soup.find(tag)
            if found is not None:
                return found
        return soup

    # ------------------------------------------------------------------
    # Fallback на стандартную библиотеку
    # ------------------------------------------------------------------

    def _clean_with_stdlib(
        self,
        html: str,
        extract_metadata: bool,
        min_len: int,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        """Очистка через html.parser (fallback без bs4)."""
        collector = _StdlibCleaner(_NOISE_TAGS, _JS_ATTRS)
        collector.feed(html)
        cleaned = collector.get_cleaned()
        metadata = collector.get_metadata() if extract_metadata else {}

        blocks: list[dict[str, Any]] = []
        for text in collector.get_text_blocks():
            if len(text) >= min_len:
                blocks.append(
                    {'tag': 'div', 'text': text, 'html': text, 'classes': []}
                )

        return cleaned, metadata, blocks


class _StdlibCleaner(HTMLParser):
    """Упрощённый очиститель HTML на стандартной библиотеке."""

    def __init__(self, noise_tags: set[str], js_attrs: re.Pattern) -> None:
        super().__init__(convert_charrefs=True)
        self._noise_tags = noise_tags
        self._js_attrs = js_attrs
        self._skip_depth = 0
        self._out: list[str] = []
        self._text_blocks: list[str] = []
        self._current_text: list[str] = []
        self._metadata: dict[str, Any] = {}
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str]]) -> None:
        if tag in self._noise_tags:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == 'title':
            self._in_title = True
        filtered = [(k, v) for k, v in attrs if not self._js_attrs.match(k)]
        attr_str = ''.join(f' {k}="{v}"' for k, v in filtered)
        self._out.append(f'<{tag}{attr_str}>')

    def handle_endtag(self, tag: str) -> None:
        if tag in self._noise_tags:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == 'title':
            self._in_title = False
        self._out.append(f'</{tag}>')
        if tag in ('article', 'section', 'div', 'p'):
            text = ' '.join(self._current_text).strip()
            if text:
                self._text_blocks.append(text)
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self._metadata['title'] = data.strip()
        self._current_text.append(data)
        self._out.append(data)

    def get_cleaned(self) -> str:
        return ''.join(self._out)

    def get_metadata(self) -> dict[str, Any]:
        return self._metadata

    def get_text_blocks(self) -> list[str]:
        return self._text_blocks
