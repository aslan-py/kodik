"""
Базовый класс для всех парсеров системы конкурентной разведки.

Определяет единый контракт, которому должны следовать все парсеры
независимо от источника данных (fedresurs, hh.ru, новости, суды и т.д.).
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# ЕДИНЫЙ ВЫХОДНОЙ ФОРМАТ ДЛЯ ВСЕХ ПАРСЕРОВ
# ============================================================================


class ParsedItem(BaseModel):
    """
    Одна единица информации (вакансия, новость, компания, судебное дело).

    Это минимальный набор полей, который должен вернуть каждый парсер.
    Все специфичные для источника данные помещаются в extra.
    """

    # Обязательные поля
    url: str = Field(..., description='Ссылка на КОНКРЕТНОЕ событие')
    title: str = Field(..., description='Заголовок события')

    # Опциональные поля
    text: str | None = Field(None, description='Тело/описание события')
    published_at: str | None = Field(
        None, description='Сырая дата (как пришла с сайта)'
    )
    region: str | None = Field(None, description='Сырое имя региона')
    media_name: str | None = Field(None, description='Название СМИ/публикатора')

    # Специфичные для источника данные
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description='Источник-специфичные поля (зарплата, статус, ИНН и т.д.)',
    )

    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                'url': 'https://fedresurs.ru/company/123',
                'title': 'ООО "Ромашка"',
                'text': 'Полное описание компании...',
                'published_at': '18.07.2026',
                'region': 'г. Москва',
                'media_name': None,
                'extra': {
                    'inn': '7712345678',
                    'status': 'Действующее',
                    'director': 'Иванов И.И.',
                },
            }
        }
    )


class ParsedResponse(BaseModel):
    """
    Результат одного похода на URL (одной выгрузки).

    Один запрос может вернуть несколько событий (например, список вакансий
    или список компаний). Каждое событие -> отдельный ParsedItem.
    """

    meta: dict[str, Any] = Field(
        ...,
        description='Метаданные запроса (search_task_id, источник, '
        'конкурент, триггер)',
    )
    items: list[ParsedItem] = Field(
        ..., description='Список извлеченных событий'
    )

    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                'meta': {
                    'search_task_id': 1,
                    'source': 'fedresurs.ru',
                    'competitor': 'Бегемот',
                    'trigger': 'ООО Ромашка',
                    'fetched_at': '2026-07-18T10:00:00Z',
                },
                'items': [
                    {
                        'url': 'https://fedresurs.ru/company/123',
                        'title': 'ООО "Ромашка"',
                        'text': 'Полное описание...',
                        'published_at': '18.07.2026',
                        'region': 'г. Москва',
                        'media_name': None,
                        'extra': {
                            'inn': '7712345678',
                            'status': 'Действующее',
                        },
                    }
                ],
            }
        }
    )


# ============================================================================
# БАЗОВЫЙ КЛАСС ПАРСЕРА (КОНТРАКТ)
# ============================================================================


class BaseParser(ABC):
    """
    Абстрактный базовый класс для всех парсеров.

    Все парсеры должны наследовать этот класс и реализовать:
    - parse(): основная логика парсинга
    - get_source_name(): имя источника
    - get_parser_type(): тип парсера (api/rpa)
    """

    @abstractmethod
    async def parse(self, url: str, **kwargs) -> ParsedResponse:
        """
        Выполнить парсинг URL и вернуть структурированные данные.

        Args:
            url: URL для парсинга
            **kwargs: Дополнительные параметры:
                - search_task_id: ID задачи (для meta)
                - competitor: имя конкурента (для meta)
                - trigger: поисковый запрос (для meta)
                - inn: ИНН (для fedresurs)
                - name: название (для fedresurs)
                - ... другие параметры

        Returns:
            ParsedResponse: Структурированный результат

        Raises:
            Exception: При любой ошибке парсинга
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Вернуть имя источника (например, 'fedresurs.ru', 'hh.ru').

        Returns:
            str: Уникальное имя источника
        """
        pass

    @abstractmethod
    def get_parser_type(self) -> str:
        """
        Вернуть тип парсера: 'api' или 'rpa'.

        Returns:
            str: 'api' для API-парсеров, 'rpa' для RPA-парсеров
        """
        pass

    def get_parser_info(self) -> dict[str, str]:
        """
        Вернуть информацию о парсере (опционально).

        Returns:
            Dict[str, str]: Информация о парсере
        """
        return {
            'source': self.get_source_name(),
            'type': self.get_parser_type(),
            'class': self.__class__.__name__,
        }


# ============================================================================
# УТИЛИТЫ ДЛЯ РАБОТЫ С ПАРСЕРАМИ
# ============================================================================


class ParserFactory:
    """
    Фабрика для создания парсеров по имени источника.
    """

    _parsers: ClassVar[dict[str, type]] = {}

    @classmethod
    def register(cls, source_name: str, parser_class: type) -> None:
        """Зарегистрировать парсер."""
        cls._parsers[source_name] = parser_class

    @classmethod
    def get_parser(cls, source_name: str, **kwargs) -> BaseParser:
        """
        Получить экземпляр парсера по имени источника.

        Args:
            source_name: Имя источника ('fedresurs.ru', 'hh.ru', ...)
            **kwargs: Параметры для парсера (headless, proxy, ...)

        Returns:
            BaseParser: Экземпляр парсера

        Raises:
            ValueError: Если парсер не найден
        """
        parser_class = cls._parsers.get(source_name)
        if parser_class is None:
            raise ValueError(
                f"Parser for source '{source_name}' not registered"
            )
        return parser_class(**kwargs)

    @classmethod
    def list_sources(cls) -> list[str]:
        """Вернуть список всех зарегистрированных источников."""
        return list(cls._parsers.keys())
