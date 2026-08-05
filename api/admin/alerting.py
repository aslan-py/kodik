"""Раздел «Настройки алертинга» (BP-5).

Типы значимых событий и слова-маркеры к ним, каналы доставки и матрица
правил: кому и куда слать при каком типе и приоритете.

Правила заводятся и из карточки типа события (инлайн), и отдельным списком.

Порог значимости живёт здесь, а не в коде: значимо то событие, для которого
нашлась строка routing_rule (см. src/bp5/BP5_README.md).
"""

from fastadmin import WidgetType, register

from api.admin.base import (
    MENU_ADMIN_ALERTING,
    KodikInlineModelAdmin,
    KodikModelAdmin,
    related,
)
from core.database import AsyncSessionLocal
from src.bp5.models import Channel, EventType, RoutingRule

_RULE_LABELS = {
    'id': 'Идентификатор',
    'event_type': 'Тип события',
    'priority': 'Приоритет',
    'user': 'Получатель',
    'channel': 'Канал',
    'mode': 'Режим доставки',
    'is_active': 'Активно',
}


class RoutingRuleInline(KodikInlineModelAdmin):
    """Правила маршрутизации прямо на странице типа события."""

    model = RoutingRule
    verbose_name = 'Правило'
    verbose_name_plural = 'Правила маршрутизации'
    list_display = ('id', 'priority', 'user', 'channel', 'mode', 'is_active')
    list_display_labels = _RULE_LABELS
    list_select_related = ('user', 'channel')
    max_num = 50

    user = related('user')
    channel = related('channel')


@register(EventType, sqlalchemy_sessionmaker=AsyncSessionLocal)
class EventTypeAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_ALERTING
    verbose_name = 'Тип события'
    verbose_name_plural = 'Типы событий'

    list_display = ('id', 'name', 'keywords', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'name': 'Название типа',
        'keywords': 'Слова-маркеры',
        'is_active': 'Активен',
    }
    list_filter = ('is_active',)
    search_fields = ('name',)
    search_help_text = 'Поиск по названию типа события'
    ordering = ('name',)
    inlines = (RoutingRuleInline,)

    formfield_overrides = {  # noqa: RUF012
        'name': (
            WidgetType.Input,
            {'placeholder': 'Как называем тип, например: выигранный тендер'},
        ),
        'keywords': (
            WidgetType.Select,
            {
                'mode': 'tags',
                'placeholder': (
                    'Слова, по которым ловим событие в заголовке: тендер, '
                    'контракт, закупка. Введите слово и нажмите Enter'
                ),
            },
        ),
    }


@register(Channel, sqlalchemy_sessionmaker=AsyncSessionLocal)
class ChannelAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_ALERTING
    verbose_name = 'Канал'
    verbose_name_plural = 'Каналы доставки'

    list_display = ('id', 'name', 'is_active')
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'name': 'Название канала',
        'is_active': 'Активен',
    }
    list_filter = ('is_active',)
    search_fields = ('name',)
    search_help_text = 'Поиск по названию канала'
    ordering = ('name',)

    formfield_overrides = {  # noqa: RUF012
        'name': (
            WidgetType.Input,
            {
                'placeholder': (
                    'Куда доставляем алерт. Допустимые значения: '
                    'telegram, email, dashboard'
                )
            },
        ),
    }


@register(RoutingRule, sqlalchemy_sessionmaker=AsyncSessionLocal)
class RoutingRuleAdmin(KodikModelAdmin):
    menu_section = MENU_ADMIN_ALERTING
    verbose_name = 'Правило'
    verbose_name_plural = 'Маршрутизация'

    list_display = (
        'id',
        'event_type',
        'priority',
        'user',
        'channel',
        'mode',
        'is_active',
    )
    list_display_labels = _RULE_LABELS
    # Без этого obj.event_type после закрытия сессии не прочитается.
    list_select_related = ('event_type', 'user', 'channel')
    list_filter = ('event_type', 'priority', 'channel', 'mode', 'is_active')
    ordering = ('id',)

    event_type = related('event_type')
    user = related('user')
    channel = related('channel')
