"""Извлечение и оценка полноты текста статьи из HTML."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from . import constants

logger = logging.getLogger(__name__)


def _extract_main_content(html: str) -> str | None:
    """Детерминированно извлекает основной контент статьи (Фича 2).

    Пытается использовать ``trafilatura`` (или ``readability-lxml``), если
    они установлены — опциональные зависимости. Это даёт полный текст
    статьи без затрат токенов LLM и работает даже без LLM-конфига. При
    отсутствии библиотек возвращает ``None`` (каскад идёт дальше к LLM).
    """
    try:
        import trafilatura  # type: ignore

        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if extracted and len(extracted) >= constants.MIN_ARTICLE_TEXT_LENGTH:
            return extracted.strip()
    except Exception as e:
        # ImportError (пакет не установлен) выглядит так же, как ошибка
        # парсинга конкретной страницы — не отличить без лога. Раньше это
        # приводило к тому, что весь каскад молча уходил в LLM для КАЖДОЙ
        # статьи, даже когда readability/trafilatura реально не установлены
        # (см. REFACTORING_PLAN.md/раздел про best-of каскад).
        logger.debug('trafilatura недоступна/ошибка извлечения: %s', e)

    try:
        from readability import Document  # type: ignore

        doc = Document(html)
        text = doc.summary(html_partial=True)
        soup = BeautifulSoup(text, 'html.parser')
        content = soup.get_text(' ', strip=True)
        if content and len(content) >= constants.MIN_ARTICLE_TEXT_LENGTH:
            return content
    except Exception as e:
        logger.debug('readability-lxml недоступна/ошибка извлечения: %s', e)

    return None


def _plain_text(html: str) -> str:
    """Возвращает плоский текст из HTML (убирает разметку и шум)."""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(
            ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']
        ):
            tag.decompose()
        return soup.get_text(' ', strip=True)
    except Exception:
        return ''


def _looks_truncated(text: str) -> bool:
    """Возвращает True, если извлечённый текст, вероятно, обрезан.

    Длинный текст (больше ``MIN_FULL_ARTICLE_TEXT_LENGTH``), заканчивающийся
    без финального знака препинания, или текст с маркерами обрыва
    (``[...]``, ``…``) считается неполным. Такой результат нуждается в
    докачке хвоста через ``_extract_missing_tail``.
    """
    if not text:
        return False
    stripped = text.rstrip()
    if any(marker in stripped[-8:] for marker in ('...', '…', '[...]')):
        return True
    if len(stripped) < constants.MIN_FULL_ARTICLE_TEXT_LENGTH:
        return False
    return stripped[-1:] not in ('.', '!', '?')


def _is_confident_article_text(text: str | None) -> bool:
    """Возвращает True, если текст достаточно длинный и не выглядит
    обрезанным — можно останавливать каскад извлечения (CSS → readability →
    LLM) досрочно.
    """
    return (
        bool(text)
        and len(text) >= constants.MIN_FULL_ARTICLE_TEXT_LENGTH
        and not _looks_truncated(text)
    )


def _extract_title(html: str) -> str | None:
    """Возвращает текст из тега ``<title>`` HTML-страницы (или None)."""
    try:
        soup = BeautifulSoup(html or '', 'html.parser')
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except Exception:
        return None
    return None
