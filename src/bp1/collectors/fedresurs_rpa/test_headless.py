"""Тестовый скрипт для проверки парсинга fedresurs.ru в headless-режиме."""

import asyncio

from .parser import FedresursRPA
from .schemas import SearchRequest


async def main():
    """Запустить тестовый поиск и вывести результат."""
    parser = FedresursRPA(default_headless=True)

    request = SearchRequest(
        name='ООО "ПТП "СТАНДАРТ"',
        inn='9718266074',
        headless=True,
    )

    result = await parser.search(request)

    if result.success:
        print(f'\nOK: {result.name} (ИНН: {result.inn})')
        print(f'  File: {result.file_path}')
        print(f'  Status: {result.status}')
        print(f'  Published at: {result.published_at}')
        print(f'  Region: {result.region}')
        print(
            f'  Extra block: {result.extra[:100]}...'
            if result.extra
            else '  Extra: None'
        )
        data_len = len(result.raw_text) if result.raw_text else 0
        print(f'  Data length: {data_len} chars')
        if result.raw_text:
            print(f'  Preview: {result.raw_text[:200]}...')
    else:
        print(f'\nFAIL: {result.error}')
        print(f'  Error type: {result.error_type}')


if __name__ == '__main__':
    asyncio.run(main())
