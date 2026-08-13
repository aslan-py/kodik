#!/usr/bin/env python3
"""
example.py — простой пример работы с DeepSeek для извлечения данных из HTML.

Запуск (из корня kodik/, внутри .venv-kodik):
    ../.venv-kodik/Scripts/python -m core.scripts.proba.example
"""

import asyncio
import json

import httpx
from openai import AsyncOpenAI

from core.config import settings
from src.bp1.adaptive.processing.llm import LLMClient

# === Ключи LLM (DeepSeek) — читаются из .env через core.config.settings ===
# LLM_MODEL / LLM_API_KEY / LLM_BASE_URL читаются через core.config.settings
# (pydantic-settings автоматически загружает .env из корня проекта).
api_key = settings.llm_api_key
model = settings.llm_model
base_url = settings.llm_base_url
print(
    f'🤖 LLM клиент создан (model: {model}, base_url: {base_url}, '
    f'api_key: {api_key[:10]}...)'
)


def classify_with_llm(response: httpx.Response, url: str) -> str:
    """Очищает HTML из response, категоризирует сайт и возвращает JSON."""
    client = LLMClient(model=model, base_url=base_url, api_key=api_key)
    # Внутри метода происходит очистка (HtmlCleaner) и категоризация.
    result = asyncio.run(client.classify_with_llm(html=response.text, url=url))
    print(result)
    return result.model_dump_json(indent=2, ensure_ascii=False)


# === 1. Получение адреса сайта ===
# Для демонстрации используем реальный URL
url = 'https://kodik.ru/'
print(f'🌐 Адрес сайта: {url}')

# === 2. Получение страницы ===
print('📥 Загрузка страницы...')
try:
    # verify=False: в системном хранилище Windows нет корневого сертификата,
    # которым подписан сертификат сайта (SSL: CERTIFICATE_VERIFY_FAILED).
    # User-Agent: без него сайт отдаёт Forbidden (бот-детекция).
    response = httpx.get(
        url,
        timeout=30,
        follow_redirects=True,
        verify=False,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/126.0.0.0 Safari/537.36'
        },
    )
except Exception as e:
    print(f'❌ Ошибка загрузки: {e}')
    raise SystemExit(1) from e

# === 3. Категоризация сайта через LLMClient.classify_with_llm ===
print('🏷️ Категоризация сайта через LLM...')
classification_json = classify_with_llm(response, url)
print('📊 JSON категоризации:')
print(classification_json)

# === 4. Создание промпта ===
prompt = f"""
Извлеки из HTML следующие данные:
1. Заголовок страницы (title)
2. Дату публикации (date) в формате DD.MM.YYYY
3. Текст новости

HTML:
{response.text[:4000]}

Ответь ТОЛЬКО в формате JSON:
{{"title": "...", "date": "...", "text": "..."}}
"""
print(f'📝 Создан промпт (первые 300 символов):\n{prompt[:300]}...')

# === 5. Передача промпта в LLM ===
print('📤 Отправка запроса к DeepSeek...')


async def main():
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.0,
            max_tokens=1024,
        )
        result = response.choices[0].message.content
        # === 6. Получение ответа ===
        print('✅ Получен ответ от LLM:')
        print(result)

        # Попытка извлечь JSON
        try:
            data = json.loads(
                result.removeprefix('```json\n').removesuffix('\n```')
            )
            print('\n📊 Структурированные данные:')
            for key, value in data.items():
                print(f'  {key}: {value}')
        except Exception as e:
            print(f'⚠️  Не удалось распарсить JSON: {e}')
            print(f'Сырой ответ: {result}')

    except Exception as e:
        print(f'❌ Ошибка при запросе к DeepSeek: {e}')


asyncio.run(main())
