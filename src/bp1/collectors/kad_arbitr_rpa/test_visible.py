"""Тестовый скрипт для проверки парсинга kad.arbitr.ru в видимом режиме.

Использование:
    cd kodik
    python -m src.bp1.collectors.kad_arbitr_rpa.test_visible

Внимание: браузер откроется в видимом окне (headless=False).
Это полезно для отладки селекторов и визуального контроля.
"""

import asyncio

from .parser import KadArbitrParser
from .schemas import ParsingRequest


async def main() -> None:
    """Запустить тестовый поиск в видимом режиме и вывести результат."""
    parser = KadArbitrParser()

    request = ParsingRequest(
        inn='9718266074',
        headless=False,
        timeout=60000,  # 2 минуты на визуальный осмотр
        use_stealth=False,  # Отключаем стелс для kad.arbitr.ru
    )

    print(f'Запуск парсинга ИНН={request.inn} (headless=False)')
    print('Браузер откроется в видимом окне. Наблюдайте за процессом.')
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
