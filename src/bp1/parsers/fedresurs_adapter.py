"""
Адаптер для fedresurs.ru, реализующий интерфейс BaseParser.

Использует существующий пакет fedresurs_rpa как внутренний движок.
Поиск осуществляется по ИНН компании.
"""

from datetime import UTC, datetime

from ..base_parser import BaseParser, ParsedItem, ParsedResponse
from ..collectors.fedresurs_rpa import (
    FedresursRPA,
    SearchRequest,
    SearchResult,
)
from ..collectors.fedresurs_rpa.schemas import ProxyConfig


class FedresursAdapter(BaseParser):
    """
    Адаптер для fedresurs.ru.

    Пример использования:
        parser = FedresursAdapter(headless=True)
        result = await parser.parse(
            url="https://fedresurs.ru",
            inn="7712345678",
            name='ООО "Ромашка"',
            search_task_id=1,
            competitor='ООО "Ромашка"'
        )
    """

    # fedresurs выполняет поиск по ИНН компании — без него RPA-сценарий
    # падает (Frame.fill() без value). Декларируем обязательность для
    # предварительной валидации в AdaptiveRunner.run_task.
    required_kwargs: tuple[str, ...] = ('inn',)

    def __init__(
        self,
        headless: bool = True,
        proxy: ProxyConfig | None = None,
        timeout: int = 60000,
    ):
        """
        Инициализация адаптера.

        Args:
            headless: Запускать браузер в headless-режиме
            proxy: Прокси-конфигурация
            timeout: Таймаут в миллисекундах
        """
        self._engine = FedresursRPA(
            default_headless=headless,
            default_proxy=proxy,
        )
        self._timeout = timeout
        self._headless = headless
        self._proxy = proxy

    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        """
        Выполнить поиск компании на fedresurs.ru по ИНН.

        Ожидаемые kwargs:
            - inn: ИНН для поиска (str, обязательный)
            - name: Название компании (str)
            - search_task_id: ID задачи (для meta)
            - competitor: имя конкурента (для meta)

        Args:
            url: Базовый URL (https://fedresurs.ru)
            **kwargs: Параметры поиска

        Returns:
            ParsedResponse: Структурированный результат

        Raises:
            Exception: Если парсинг не удался
        """
        # 1. Извлекаем параметры
        inn = kwargs.get('inn')
        name = kwargs.get('name', '')
        search_task_id = kwargs.get('search_task_id')
        competitor = kwargs.get('competitor')

        # 2. Формируем запрос для внутреннего движка
        request = SearchRequest(
            name=name,
            inn=inn,
            headless=self._headless,
            proxy=self._proxy,
            timeout=self._timeout,
        )

        # 3. Выполняем поиск
        result: SearchResult = await self._engine.search(request)

        # 4. Проверяем результат
        if not result.success:
            raise Exception(
                f'Fedresurs parsing failed: {result.error} '
                f'(type: {result.error_type})'
            )

        # 5. Трансформируем SearchResult -> ParsedResponse
        # Собираем все данные в один item
        item = ParsedItem(
            # URL карточки компании (страница с детальной информацией)
            url=result.url,
            title=result.status,
            text=result.raw_text,
            published_at=result.published_at,
            region=result.region,
            media_name=None,  # У fedresurs нет СМИ
            extra={
                'director_info': result.extra,  # Блок с руководителем
                # служебное поле для копирования HTML
                'file_path': result.file_path,
            },
        )

        # Формируем ответ
        return ParsedResponse(
            meta={
                'search_task_id': search_task_id,
                'source': self.get_source_name(),
                'competitor': competitor,
                'trigger': None,
                # URL страницы поиска (entities?searchString=...)
                'source_request_url': result.search_url,
                'fetched_at': datetime.now(UTC).isoformat(),
            },
            items=[item],
        )

    def get_source_name(self) -> str:
        """Вернуть имя источника."""
        return 'fedresurs.ru'

    def get_parser_type(self) -> str:
        """Вернуть тип парсера."""
        return 'rpa'  # fedresurs требует RPA с обходом QRATOR
