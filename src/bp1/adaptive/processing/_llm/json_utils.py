"""Утилиты разбора JSON-ответов LLM.

Устойчивый к markdown-обёртке парсер. Вынесен из ``llm.py``, чтобы им
пользовались ``LLMClient`` и ``AIAgent`` без нарушения инкапсуляции.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Соответствует блоку ```json {...} ```, либо блоку ```{...}```,
# либо просто JSON-объекту, обёрнутому в фигурные скобки.
_JSON_BLOCK_RE = re.compile(
    r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL | re.IGNORECASE
)


def parse_json(content: str) -> dict[str, Any]:
    """Извлекает JSON-объект из ответа LLM.

    Пытается распарсить ``content`` как есть. Если это не удалось —
    ищет JSON-блок внутри markdown-обёртки (`````json ... `````) либо
    первый ``{...}`` фрагмент в тексте.

    Args:
        content: Ответ модели (возможно, с пояснениями или обёрткой).

    Returns:
        dict: распарсенный JSON-объект, или ``{}`` при неудаче.
    """
    content = content.strip()
    if not content:
        return {}

    # 1) Прямой разбор.
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2) Markdown-блок ```json {...} ```.
    match = _JSON_BLOCK_RE.search(content)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 3) Первый {...} фрагмент в тексте.
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end > start:
        try:
            parsed = json.loads(content[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {}
