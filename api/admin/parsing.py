"""Раздел «Настройки парсинга» (BP-1).

Кого ищем (competitor), где (source), по каким словам (trigger) и матрица
их сочетаний (search_task) — именно её перебирает Celery Beat.

Связанное заполнение сделано инлайнами: на странице конкурента (а также
источника и триггера) лежит таблица его задач сбора — можно завести их не
уходя со страницы. Обратный путь тоже есть: на странице search_task
конкурент/источник/триггер выбираются из выпадающих списков с поиском по
названию (поиск работает благодаря `search_fields` у этих справочников).
"""

from fastadmin import WidgetType, register

from api.admin.base import (
    MENU_ADMIN_PARSING,
    KodikInlineModelAdmin,
    KodikModelAdmin,
)
from core.database import AsyncSessionLocal
from src.bp1.models import Competitor, SearchTask, Source, Trigger

_TASK_LABELS = {
    'id': 'Идентификатор',
    'competitor': 'Конкурент',
    'source': 'Источник',
    'trigger': 'Триггер',
    'is_active': 'Активна',
}


class SearchTaskInline(KodikInlineModelAdmin):
    """Задачи сбора прямо на странице конкурента/источника/триггера.

    `fk_name` не указываем: FastAdmin сам определяет, по какому из трёх FK
    связывать, — у каждого родителя совпадает ровно один.
    """

    model = SearchTask
    verbose_name = 'Задача сбора'
    verbose_name_plural = 'Задачи сбора'
    list_display = ('id', 'competitor', 'source', 'trigger', 'is_active')
    list_display_labels = _TASK_LABELS
    list_select_related = ('competitor', 'source', 'trigger')
    max_num = 50


@register(Competitor, sqlalchemy_sessionmaker=AsyncSessionLocal)
class CompetitorAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_PARSING
    verbose_name = 'Конкурент'
    verbose_name_plural = 'Конкуренты'

    list_display = ('id', 'name', 'inn', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'name': 'Название компании',
        'inn': 'ИНН',
        'is_active': 'Активен',
    }
    list_filter = ('name', 'inn', 'is_active')
    search_fields = ('name', 'inn')
    search_help_text = 'Поиск по названию или ИНН'
    ordering = ('name',)
    inlines = (SearchTaskInline,)

    formfield_overrides = {  # noqa: RUF012
        'name': (
            WidgetType.Input,
            {'placeholder': 'Компания, которую мониторим, например: АвтоМЛ'},
        ),
        'inn': (
            WidgetType.Input,
            {
                'placeholder': (
                    'ИНН для поиска по гос-реестрам, 10 или 12 цифр, '
                    'например: 7712345678. Можно не заполнять'
                )
            },
        ),
    }


@register(Source, sqlalchemy_sessionmaker=AsyncSessionLocal)
class SourceAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_PARSING
    verbose_name = 'Источник'
    verbose_name_plural = 'Источники'

    list_display = ('id', 'name', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'name': 'Адрес источника',
        'is_active': 'Активен',
    }
    list_filter = ('name', 'is_active')
    search_fields = ('name',)
    search_help_text = 'Поиск по адресу источника'
    ordering = ('name',)
    inlines = (SearchTaskInline,)

    formfield_overrides = {  # noqa: RUF012
        'name': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Сайт, который парсим, например: '
                    'https://newssearch.yandex.ru или hh.ru'
                )
            },
        ),
    }


@register(Trigger, sqlalchemy_sessionmaker=AsyncSessionLocal)
class TriggerAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_PARSING
    verbose_name = 'Триггер'
    verbose_name_plural = 'Триггеры'

    list_display = ('id', 'keyword', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'keyword': 'Ключевое слово',
        'is_active': 'Активен',
    }
    list_filter = ('keyword', 'is_active')
    search_fields = ('keyword',)
    search_help_text = 'Поиск по ключевому слову'
    ordering = ('keyword',)
    inlines = (SearchTaskInline,)

    formfield_overrides = {  # noqa: RUF012
        'keyword': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Слово для поиска на источнике, например: '
                    'искусственный интеллект, тендер, утечка данных'
                )
            },
        ),
    }


@register(SearchTask, sqlalchemy_sessionmaker=AsyncSessionLocal)
class SearchTaskAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_PARSING
    verbose_name = 'Задача сбора'
    verbose_name_plural = 'Задачи сбора'

    list_display = ('id', 'competitor', 'source', 'trigger', 'is_active')
    list_display_labels = _TASK_LABELS
    list_select_related = ('competitor', 'source', 'trigger')
    list_filter = ('competitor', 'source', 'trigger', 'is_active')
    ordering = ('id',)
