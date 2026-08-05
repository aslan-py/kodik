"""Витрина (BP-4) и план действий (BP-6).

`ActionItem` — единственная таблица этой пары, которую заполняет человек:
аналитик заводит задачу по событию витрины, отдел двигает статус. Полный
CRUD.

`ShowcaseEvent` — только просмотр, и это осознанно. Витрина производна от
`categorized_event`: прямой UPDATE строки витрины разъедется с источником
правды и будет затёрт следующим инкрементом BP-4 (ABOUT.md, BP-4 п.5).
Правка разметки идёт через `PATCH /showcase/{id}`, где write-through в
`categorized_event` + зеркалирование реализованы один раз
(api/crud/showcase.py::ShowcaseCRUD.update).
"""

from fastadmin import WidgetType, register

from api.admin.base import (
    MENU_ACTIONS,
    MENU_SHOWCASE,
    KodikModelAdmin,
    ReadOnlyModelAdmin,
)
from core.database import AsyncSessionLocal
from src.bp4.models import ShowcaseEvent
from src.bp6.models import ActionItem


@register(ShowcaseEvent, sqlalchemy_sessionmaker=AsyncSessionLocal)
class ShowcaseEventAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_SHOWCASE
    verbose_name = 'Событие витрины'
    verbose_name_plural = 'События'

    list_display = (
        'id',
        'published_at',
        'title',
        'competitor',
        'priority',
        'category',
        'region',
        'department',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'published_at': 'Дата события',
        'title': 'Заголовок',
        'competitor': 'Конкурент',
        'priority': 'Приоритет',
        'category': 'Категория',
        'region': 'Регион',
        'department': 'Отдел',
        'tonality': 'Тональность',
        'media': 'СМИ',
        'macro_region': 'Федеральный округ',
        'source_url': 'Ссылка на событие',
        'media_index': 'Медиаиндекс',
        'action': 'Требуемое действие',
        'deadline': 'Срок реакции',
        'comment': 'Комментарий',
        'updated_at': 'Обновлено',
        'alerted_at': 'Проверено алертингом',
    }
    list_filter = ('priority', 'category', 'tonality', 'department')
    search_fields = ('title', 'competitor', 'region', 'media')
    search_help_text = 'Поиск по заголовку, конкуренту, региону или СМИ'
    ordering = ('-published_at',)


@register(ActionItem, sqlalchemy_sessionmaker=AsyncSessionLocal)
class ActionItemAdmin(KodikModelAdmin):
    menu_section = MENU_ACTIONS
    verbose_name = 'Задача'
    verbose_name_plural = 'Задачи'

    list_display = (
        'id',
        'task',
        'department',
        'assigned_user',
        'status',
        'deadline',
        'created_at',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'task': 'Задача',
        'showcase_event': 'Событие витрины',
        'department': 'Ответственный отдел',
        'assigned_user': 'Исполнитель',
        'status': 'Статус',
        'deadline': 'Срок',
        'expected_result': 'Ожидаемый результат',
        'created_at': 'Заведена',
        'updated_at': 'Обновлена',
    }
    list_select_related = ('department', 'assigned_user')
    list_filter = ('status', 'department', 'assigned_user')
    search_fields = ('task', 'expected_result')
    search_help_text = 'Поиск по задаче или ожидаемому результату'
    ordering = ('-id',)
    # Проставляется базой при вставке — показываем, но не даём править.
    readonly_fields = ('created_at',)

    formfield_overrides = {  # noqa: RUF012
        'task': (
            WidgetType.TextArea,
            {
                'placeholder': (
                    'Что конкретно сделать, например: подготовить ответ '
                    'на публикацию в СМИ до конца недели'
                )
            },
        ),
        'expected_result': (
            WidgetType.TextArea,
            {
                'placeholder': (
                    'Чем закончить, например: опубликован пресс-релиз, '
                    'согласован с юристами'
                )
            },
        ),
    }
