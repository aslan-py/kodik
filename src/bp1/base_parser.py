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


class ParsedMeta(BaseModel):
    """
    Метаданные одной выгрузки (``raw_data.meta``) — контракт BP-1 -> BP-2.

    Состав и порядок полей закреплены ``ABOUT_PROJECT/ABOUT.md`` (раздел
    BP-1, «Содержимое raw_data»). Список полей закрыт (``extra='forbid'``):
    всё, что не факт о самом запросе (сработавшая стратегия, статус
    качества, служебные счётчики парсинга), относится к
    ``ParsedResponse.metrics``, а не сюда. Раньше это правило не
    соблюдалось — адаптивный мост дописывал в ``meta`` собственные
    диагностические поля (``probed_url``/``strategy_used``/
    ``quality_status``), и контракт для BP-2 расходился с ABOUT.md без
    единого места, которое бы это ловило.
    """

    search_task_id: int | None = Field(
        None, description='Ссылка на задачу-конфигурацию (= ключ в Redis)'
    )
    source: str = Field(..., description='С какого ресурса собрали')
    competitor: str = Field(..., description='По какому конкуренту искали')
    trigger: str | None = Field(
        None, description='По какому слову искали (может быть null)'
    )
    source_request_url: str = Field(
        ..., description='НАШ поисковый запрос, один на всю выгрузку'
    )
    fetched_at: str = Field(
        ...,
        description='Время съёма; в content-хэш не включается (иначе '
        'всегда changed)',
    )

    model_config = ConfigDict(extra='forbid')


class ParsedMetrics(BaseModel):
    """
    Служебные поля, результаты парсинга и метрики (``raw_data.metrics``).

    Не входит в бизнес-контракт BP-2 (см. ``ParsedMeta``/``ParsedItem``) —
    только для аудита и наблюдаемости (Шаг 20 плана рефакторинга bp1, T6).
    Список полей открыт (``extra='allow'``): разные парсеры/движки
    (RPA-адаптеры, адаптивный сбор) собирают разную диагностику, и не у
    каждого прогона есть все поля — в отличие от ``ParsedMeta``/
    ``ParsedItem``, здесь фиксировать закрытый список избыточно и вредно
    (пришлось бы трогать контракт при каждой новой метрике).
    """

    probed_url: str | None = Field(
        None, description='URL после поиска (пробинга); null — fallback'
    )
    strategy_used: str | None = Field(
        None, description='Реально сработавшая стратегия сбора'
    )
    quality_status: str | None = Field(
        None, description='Итог DataQualityGate: ok/low_quality'
    )
    quality_levels: dict[str, Any] | None = Field(
        None, description='Пер-уровневая сводка DataQualityGate'
    )
    relevance_mode: str | None = Field(
        None, description='Режим фильтра релевантности: off/filter/rank'
    )
    news_total: int | None = Field(
        None, description='Сколько новостей найдено до фильтрации'
    )
    relevance_filtered: int | None = Field(
        None, description='Сколько новостей отсеяно фильтром релевантности'
    )
    file_saved: bool | None = Field(
        None, description='Удалось ли сохранить HTML-снимок на диск'
    )

    model_config = ConfigDict(extra='allow')


class ParsedItem(BaseModel):
    """
    Одна единица информации (вакансия, новость, компания, судебное дело).

    Это минимальный набор полей, который должен вернуть каждый парсер.
    Все специфичные для источника данные помещаются в extra. Список
    полей на верхнем уровне закрыт (``extra='forbid'``) — источник-
    специфичные факты обязаны идти через ``extra``, а не через новое поле
    рядом с ``url``/``title``/...; так контракт нельзя случайно расширить
    мимо ``extra``.
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
        extra='forbid',
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
        },
    )


class ParsedResponse(BaseModel):
    """
    Результат одного похода на URL (одной выгрузки).

    Один запрос может вернуть несколько событий (например, список вакансий
    или список компаний). Каждое событие -> отдельный ParsedItem.

    Это ЕДИНСТВЕННЫЙ путь, которым ``raw_data`` попадает в БД (см.
    ``src/bp1/storage.py::RawDataService.persist`` — сохраняет
    ``response.model_dump()`` как есть). Persisted raw_data (файл на диске
    и ``RawItem.raw_data`` в БД) содержит РОВНО два раздела: ``meta``
    (факты о запросе) и ``items`` (факты о событиях) — соответствует
    контракту из ``ABOUT_PROJECT/ABOUT.md``. ``metrics`` — диагностика
    текущего прогона (реально сработавшая стратегия, статус Quality Gate
    и т.п.), доступна в памяти как ``response.metrics`` (используется
    ``adaptive/integration/runner.py`` для собственных отчётов), но
    исключена из ``model_dump()`` тем же способом, что и
    ``html_file_path`` — см. ``exclude=True`` ниже.
    """

    meta: ParsedMeta = Field(
        ...,
        description='Метаданные запроса (search_task_id, источник, '
        'конкурент, триггер)',
    )
    items: list[ParsedItem] = Field(
        ..., description='Список извлеченных событий'
    )
    # Диагностика прогона (не бизнес-данные) — доступна в памяти вызывающему
    # коду (runner.py), но исключена из model_dump()/persisted raw_data:
    # ABOUT.md документирует raw_data строго как meta+items.
    metrics: ParsedMetrics = Field(
        default_factory=ParsedMetrics,
        exclude=True,
        description='Служебные поля, результаты парсинга и метрики сбора '
        '(не относятся к бизнес-данным событий; не сериализуется в '
        'persisted raw_data)',
    )
    # Внутренний путь к скачанному HTML-снимку — только для копирования
    # файла раннером/сервисом персистентности (см. storage.py). Не должен
    # попадать в persisted raw_data, поэтому исключён из model_dump().
    html_file_path: str | None = Field(default=None, exclude=True)

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'example': {
                'meta': {
                    'search_task_id': 1,
                    'source': 'fedresurs.ru',
                    'competitor': 'Бегемот',
                    'trigger': 'ООО Ромашка',
                    'source_request_url': 'https://fedresurs.ru/entities?'
                    'searchString=ООО+Ромашка',
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
                # metrics не показан здесь: исключён из model_dump()
                # (exclude=True), поэтому не попадает в persisted raw_data.
            }
        },
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

    # Параметры kwargs, обязательные для parse(). Специализированные
    # RPA-парсеры (например, fedresurs) переопределяют этот атрибут, чтобы
    # вызвавший код мог провалидировать предусловия до запуска браузера,
    # не допуская провалов вроде Frame.fill() без value из-за отсутствия ИНН.
    required_kwargs: ClassVar[tuple[str, ...]] = ()

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
