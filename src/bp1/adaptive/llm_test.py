#!/usr/bin/env python3
# src/bp1/adaptive/llm_test.py
"""
Smoke-тест LLM-модуля пакета BP-1 Adaptive через LLMClient.

Берёт HTML любой страницы из папки data/html_pages и передаёт его
в LLMClient._llm_analyze для анализа структуры через LLM.

Параметры:
    expected_fields = ''            (пустой список полей)
    competitor      = 'ООО "Архитект ИИ"'

Использование (из корня проекта kodik/):
    python -m src.bp1.adaptive.llm_test
"""

# from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

import litellm

from src.bp1.adaptive.llm import LLMClient

# Корень проекта kodik/ — четыре уровня вверх от этого файла.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Добавляем корень проекта в PYTHONPATH, чтобы работал импорт src.*
# при запуске файла напрямую (python src/bp1/adaptive/llm_test.py).
sys.path.insert(0, str(PROJECT_ROOT))


ENV_PATH = PROJECT_ROOT / '.env'

# Папка с сохранёнными HTML-страницами (см. core.config: bp1_html_dir).
HTML_DIR = PROJECT_ROOT / 'src' / 'bp1' / 'data' / 'html_pages'

COMPETITOR = 'ООО "Архитект ИИ"'
EXPECTED_FIELDS: list[str] = []  # expected_fields = ''


def _load_env() -> None:
    """Загружает переменные LLM_* из .env в os.environ (без python-dotenv)."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Загружаем только LLM-переменные, чтобы не затирать окружение.
        if key.startswith('LLM_') or key == 'OPENAI_API_KEY':
            os.environ.setdefault(key, value)


def _pick_html() -> Path:
    """Возвращает первый HTML-файл из data/html_pages."""
    if not HTML_DIR.exists():
        raise FileNotFoundError(f'Папка не найдена: {HTML_DIR}')
    files = sorted(HTML_DIR.glob('*.html'))
    if not files:
        raise FileNotFoundError(f'В папке нет HTML-файлов: {HTML_DIR}')
    return files[0]


async def main() -> None:
    """Точка входа smoke-теста."""
    _load_env()

    html_path = _pick_html()
    html = html_path.read_text(encoding='utf-8', errors='replace')

    print(f'HTML-файл: {html_path.name}')
    print(f'Размер HTML: {len(html)} символов')
    print(f'Competitor: {COMPETITOR}')
    print(f'Expected fields: {EXPECTED_FIELDS or "(пусто)"}')
    print(f'Модель: {os.getenv("LLM_MODEL", "gpt-4o-mini")}')
    print('-' * 60)

    if not (os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY')):
        print('ОШИБКА: не задан LLM_API_KEY или OPENAI_API_KEY.')
        print('Проверьте переменные в .env или задайте их в окружении.')
        sys.exit(1)

    client = LLMClient()
    try:
        litellm._turn_on_debug()
        config = await client._llm_analyze(
            html=html[20000:21000],
            competitor=COMPETITOR,
            expected_fields=EXPECTED_FIELDS,
        )
    except Exception as e:
        print(f'ОШИБКА запроса к модели: {type(e).__name__}: {e}')
        sys.exit(1)

    print('Ответ LLM (AdapterConfig):')
    print(config.model_dump_json(indent=2))
    print('-' * 60)
    print('OK: LLM-модуль работает.')


if __name__ == '__main__':
    asyncio.run(main())
