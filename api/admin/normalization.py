"""Раздел «Настройки справочников» (BP-2 и BP-3).

Что отсеиваем и как размечаем: регионы, чёрный список доменов, стоп-слова,
лимиты анти-шума (BP-2), категории и отделы (BP-3).

Region — без `is_active`: это статический справочник городов, выключать в
нём нечего (см. src/bp2/models.py::Region).
"""

from fastadmin import WidgetType, register

from api.admin.base import MENU_ADMIN_REFERENCES, KodikModelAdmin
from core.database import AsyncSessionLocal
from src.bp2.models import BlackDomain, Region, StopWord, TopicLimit
from src.bp3.models import Category, Department


@register(Region, sqlalchemy_sessionmaker=AsyncSessionLocal)
class RegionAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_REFERENCES
    verbose_name = 'Регион'
    verbose_name_plural = 'Регионы'

    list_display = (
        'id',
        'name_display',
        'name_aliases',
        'macro_region',
        'latitude',
        'longitude',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'name_display': 'Название',
        'name_aliases': 'Варианты написания',
        'macro_region': 'Федеральный округ',
        'latitude': 'Широта',
        'longitude': 'Долгота',
    }
    list_filter = ('name_display', 'macro_region')
    search_fields = ('name_display', 'macro_region')
    search_help_text = 'Поиск по названию или федеральному округу'
    ordering = ('name_display',)

    formfield_overrides = {  # noqa: RUF012
        'name_display': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Каноническое имя для витрины и карты, например: Волгоград'
                )
            },
        ),
        'name_aliases': (
            WidgetType.Select,
            {
                'mode': 'tags',
                'placeholder': (
                    'Варианты написания В НИЖНЕМ РЕГИСТРЕ, по ним ищем регион '
                    'в тексте: волгоград, г. волгоград, г волгоград. '
                    'Введите вариант и нажмите Enter'
                ),
            },
        ),
        'macro_region': (
            WidgetType.Input,
            {'placeholder': 'Федеральный округ, например: ЮФО, ЦФО'},
        ),
        'latitude': (
            WidgetType.InputNumber,
            {'placeholder': 'Широта центра региона (WGS-84), например: 48.708'},
        ),
        'longitude': (
            WidgetType.InputNumber,
            {'placeholder': 'Долгота центра (WGS-84), например: 44.513'},
        ),
    }


@register(BlackDomain, sqlalchemy_sessionmaker=AsyncSessionLocal)
class BlackDomainAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_REFERENCES
    verbose_name = 'Домен в чёрном списке'
    verbose_name_plural = 'Чёрный список'

    list_display = ('id', 'domain', 'reason', 'created_at', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'domain': 'Домен',
        'reason': 'Причина',
        'created_at': 'Добавлен',
        'is_active': 'Активен',
    }
    # Дата проставляется базой при вставке — показываем, но не даём править.
    readonly_fields = ('created_at',)
    list_filter = ('domain', 'is_active')
    search_fields = ('domain', 'reason')
    search_help_text = 'Поиск по домену или причине'
    ordering = ('domain',)

    formfield_overrides = {  # noqa: RUF012
        'domain': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Домен СМИ-публикатора БЕЗ https:// и пути, '
                    'например: kompromat.ru'
                )
            },
        ),
        'reason': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Почему отсеиваем, например: компрометирующий ресурс'
                )
            },
        ),
    }


@register(StopWord, sqlalchemy_sessionmaker=AsyncSessionLocal)
class StopWordAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_REFERENCES
    verbose_name = 'Стоп-слово'
    verbose_name_plural = 'Стоп-слова'

    list_display = ('id', 'phrase', 'type', 'note', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'phrase': 'Слово или фраза',
        'type': 'Тип отсева',
        'note': 'Пояснение',
        'is_active': 'Активно',
    }
    list_filter = ('type', 'is_active')
    search_fields = ('phrase', 'note')
    search_help_text = 'Поиск по фразе или пояснению'
    ordering = ('phrase',)

    formfield_overrides = {  # noqa: RUF012
        'phrase': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Ищется как подстрока в заголовке и тексте, '
                    'например: гороскоп, реклама, крейсер'
                )
            },
        ),
        'note': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Для аналитика: от чего защищает, например: ложное '
                    'срабатывание — крейсер «Аврора» не разработчик ИИ'
                )
            },
        ),
    }


@register(TopicLimit, sqlalchemy_sessionmaker=AsyncSessionLocal)
class TopicLimitAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_REFERENCES
    verbose_name = 'Лимит анти-шума'
    verbose_name_plural = 'Лимиты анти-шума'

    list_display = ('id', 'scope', 'max_count', 'window', 'note', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'scope': 'Считаем по',
        'max_count': 'Максимум событий',
        'window': 'За период',
        'note': 'Пояснение',
        'is_active': 'Активен',
    }
    list_filter = ('scope', 'window', 'is_active')
    search_fields = ('note',)
    search_help_text = 'Поиск по пояснению'
    ordering = ('id',)

    formfield_overrides = {  # noqa: RUF012
        'max_count': (
            WidgetType.InputNumber,
            {
                'placeholder': (
                    'Сколько событий на одну группу пропускаем за период; '
                    'всё сверх — отсев, например: 5'
                )
            },
        ),
        'note': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Зачем лимит, например: один конкурент не должен '
                    'занимать половину отчёта'
                )
            },
        ),
    }


@register(Category, sqlalchemy_sessionmaker=AsyncSessionLocal)
class CategoryAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_REFERENCES
    verbose_name = 'Категория'
    verbose_name_plural = 'Категории'

    list_display = ('id', 'name', 'note', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'name': 'Название категории',
        'note': 'Определение',
        'is_active': 'Активна',
    }
    list_filter = ('name', 'is_active')
    search_fields = ('name', 'note')
    search_help_text = 'Поиск по названию или определению'
    ordering = ('name',)

    formfield_overrides = {  # noqa: RUF012
        'name': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Из закрытого списка ТЗ, например: репутационный риск'
                )
            },
        ),
        'note': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Что под неё подпадает — это определение читает LLM '
                    'при разметке'
                )
            },
        ),
    }


@register(Department, sqlalchemy_sessionmaker=AsyncSessionLocal)
class DepartmentAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_REFERENCES
    verbose_name = 'Отдел'
    verbose_name_plural = 'Отделы'

    list_display = ('id', 'name', 'note', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'name': 'Название отдела',
        'note': 'Зона ответственности',
        'is_active': 'Активен',
    }
    list_filter = ('is_active',)
    search_fields = ('name', 'note')
    search_help_text = 'Поиск по названию или зоне ответственности'
    ordering = ('name',)

    formfield_overrides = {  # noqa: RUF012
        'name': (
            WidgetType.Input,
            {'placeholder': 'Например: Юристы, PR, Аналитика, Маркетинг'},
        ),
        'note': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Какие категории ведёт, например: держат санкции и иски'
                )
            },
        ),
    }
