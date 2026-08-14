"""Построение промптов для LLM-задач (BP-1 Adaptive).

Функции собирают финальные промпты из шаблонов ``prompts.py``,
подставляя конкретные входные данные. Логика вынесена из ``llm.py``,
чтобы классы-фасады оставались тонкими.
"""

from __future__ import annotations

import json
from typing import Any

from ..chunker import Chunk
from . import prompts
from .constants import DEFAULT_FIELDS, HTML_SNIPPET_SIZE


def default_fields() -> list[str]:
    """Возвращает список полей по умолчанию (новую копию)."""
    return list(DEFAULT_FIELDS)


def build_classification_prompt(
    url: str,
    title: str,
    description: str,
    html: str,
) -> str:
    """Собирает промпт детальной классификации сайта."""
    return prompts.SITE_CLASSIFICATION_PROMPT_V2.format(
        url=url,
        title=title,
        description=description,
        html=html[:HTML_SNIPPET_SIZE],
    )


def build_analysis_prompt(
    html: str,
    competitor: str,
    expected_fields: list[str],
) -> str:
    """Собирает промпт анализа структуры страницы (один запрос)."""
    return (
        prompts._ANALYSIS_HEADER.format(
            competitor=competitor,
            expected_fields=expected_fields,
            html=html,
        )
        + prompts._ANALYSIS_RESPONSE_RULES
    )


def build_chunk_prompt(
    chunk: Chunk,
    competitor: str,
    expected_fields: list[str],
) -> str:
    """Собирает промпт анализа одного фрагмента HTML (чанка)."""
    header = (
        'Ты — эксперт по анализу HTML-страниц и извлечению '
        'структурированных данных.\n\n'
        '## Задача:\n'
        'Проанализируй фрагмент HTML-страницы и определи CSS-селекторы '
        'для извлечения данных.\n\n'
        '## Входные данные:\n'
        f'- Конкурент: {competitor}\n'
        f'- Ожидаемые поля: {expected_fields}\n'
        f'- Фрагмент HTML (часть {chunk.index}):\n'
        f'{chunk.content}\n\n'
        '## Требования:\n'
        '1. Найди контейнер, который содержит список элементов\n'
        '2. Для каждого поля определи CSS-селектор\n'
        '3. Определи схему данных (типы полей)\n\n'
    )
    response_rules = (
        '## Ответь ТОЛЬКО в формате JSON:\n'
        '{\n'
        '    "selectors": {\n'
        '        "container": "",\n'
        '        "title": "",\n'
        '        "text": "",\n'
        '        "published_at": "",\n'
        '        "region": "",\n'
        '        "media_name": "",\n'
        '        "url": "a[href]"\n'
        '    },\n'
        '    "schema": {},\n'
        '    "confidence": 0.0,\n'
        '    "metadata": {}\n'
        '}\n\n'
        '## Правила:\n'
        '1. Извлекай ТОЛЬКО из этого фрагмента\n'
        '2. Если поле не найдено, оставь пустую строку\n'
        '3. Confidence — уверенность в извлечении (0.0-1.0)'
    )
    return header + response_rules


def build_article_text_prompt(html: str) -> str:
    """Собирает промпт извлечения текста статьи."""
    return prompts.ARTICLE_TEXT_PROMPT.format(html=html)


def build_strategy_prompt(classification_json: str) -> str:
    """Собирает промпт выбора стратегии обхода."""
    return prompts.STRATEGY_CHOICE_PROMPT.format(
        classification=classification_json
    )


def build_result_analysis_prompt(
    source_name: str,
    items: list[dict[str, Any]],
) -> str:
    """Собирает промпт анализа результата парсинга."""
    examples = json.dumps(items[:3], ensure_ascii=False)
    return prompts.RESULT_ANALYSIS_PROMPT.format(
        source_name=source_name,
        item_count=len(items),
        examples=examples,
    )


def build_relevance_prompt(
    items: list[dict[str, Any]],
    competitor: str,
    trigger: str,
) -> str:
    """Собирает промпт пакетного скоринга релевантности.

    Каждый элемент содержит только ``index``/``title``/``text``, чтобы
    минимизировать объём токенов в запросе.
    """
    payload = [
        {
            'index': i,
            'title': (item.get('title') or '')[:500],
            'text': (item.get('text') or item.get('ex_text') or '')[:1500],
        }
        for i, item in enumerate(items)
    ]
    return prompts.RELEVANCE_PROMPT.format(
        competitor=competitor,
        trigger=trigger,
        items=json.dumps(payload, ensure_ascii=False),
    )


def build_enrichment_prompt(
    text: str,
    competitor: str,
    trigger: str,
) -> str:
    """Собирает промпт обогащения события структурированными полями."""
    return prompts.ENRICHMENT_PROMPT.format(
        competitor=competitor,
        trigger=trigger,
        text=text[:HTML_SNIPPET_SIZE],
    )
