"""Тестовый скрипт для проверки парсинга kad.arbitr.ru в headless-режиме.

Использование:
    cd kodik
    python -m src.bp1.collectors.kad_arbitr_rpa.test_headless
"""

import asyncio

from .parser import KadArbitrParser
from .schemas import ParsingRequest


async def main() -> None:
    """Запустить тестовый поиск в headless-режиме и вывести результат."""
    parser = KadArbitrParser()

    request = ParsingRequest(
        inn='9718266074',
        headless=True,
        timeout=120000,
        use_stealth=False,  # Выборочный стелс (без проблемных JS-инъекций)
    )

    print(f'Запуск парсинга ИНН={request.inn} (headless=True)')
    result = await parser.search_by_inn(request)

    if result.success:
        print(f'\nOK: ИНН={result.inn}')
        print(f'  File: {result.file_path}')
        print(f'  User-Agent: {result.user_agent_used}')
        print(f'  Proxy: {result.proxy_used}')
    else:
        print(f'\nFAIL: {result.error}')


if __name__ == '__main__':
    asyncio.run(main())
