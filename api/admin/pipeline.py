"""Раздел «Данные конвейера» — только просмотр (BP-1, BP-2, BP-3, BP-5, BP-7).

Слои данных, которые пишет сам конвейер. Правка руками здесь запрещена
(`ReadOnlyModelAdmin`), причины по таблицам:

- `raw_item` — «грязное» сырьё парсинга, его смысл в том, чтобы совпадать
  с тем, что реально отдал источник;
- `normalized_item` — у модели нет `updated_at`, поэтому правка постфактум
  никогда не была бы замечена повторным прогоном BP-3;
- `categorized_event` — правится через `PATCH /showcase/{id}`, иначе
  сломается зеркалирование в витрину (см. api/admin/workflow.py);
- `alert` — журнал доставки: подмена статуса задним числом испортила бы
  историю отправок;
- `source_candidate` — очередь кандидатов BP-7, её наполняет агент, а в
  `source` переносит SourceCandidatePromoter по порогу score
  (src/bp7/BP7_README.md).
"""

from fastadmin import register

from api.admin.base import MENU_PIPELINE, ReadOnlyModelAdmin
from core.database import AsyncSessionLocal
from src.bp1.models import RawItem
from src.bp2.models import NormalizedItem
from src.bp3.models import CategorizedEvent
from src.bp5.models import Alert
from src.bp7.models import SourceCandidate


@register(RawItem, sqlalchemy_sessionmaker=AsyncSessionLocal)
class RawItemAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_PIPELINE
    verbose_name = 'Сырьё парсинга'
    verbose_name_plural = 'Сырьё (BP-1)'

    list_display = (
        'id',
        'search_task',
        'status',
        'source_request_url',
        'raw_data',
        'created_at',
        'updated_at',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'search_task': 'Задача сбора',
        'status': 'Статус',
        'content_hash': 'Хэш контента',
        'raw_data': 'Сырые данные',
        'html_file_path': 'Файл HTML',
        'source_request_url': 'Запрос парсера',
        'error_message': 'Ошибка',
        'created_at': 'Собрано',
        'updated_at': 'Последняя сверка',
    }
    list_select_related = ('search_task',)
    list_filter = ('status', 'search_task')
    search_fields = ('source_request_url', 'error_message')
    search_help_text = 'Поиск по ссылке запроса или тексту ошибки'
    ordering = ('-id',)


@register(NormalizedItem, sqlalchemy_sessionmaker=AsyncSessionLocal)
class NormalizedItemAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_PIPELINE
    verbose_name = 'Нормализованное событие'
    verbose_name_plural = 'Нормализация (BP-2)'

    list_display = (
        'id',
        'published_at',
        'title',
        'competitor',
        'region',
        'source',
        'status',
        'reject_reason',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'raw_item': 'Сырьё',
        'published_at': 'Дата события',
        'title': 'Заголовок',
        'competitor': 'Конкурент',
        'region': 'Регион',
        'source': 'Источник',
        'media_name': 'СМИ',
        'media_domain': 'Домен СМИ',
        'url': 'Ссылка',
        'text': 'Текст',
        'extra': 'Доп. поля',
        'dedup_key': 'Ключ дедупликации',
        'status': 'Статус',
        'reject_reason': 'Причина отсева',
        'created_at': 'Нормализовано',
    }
    list_select_related = ('competitor', 'region', 'source')
    list_filter = (
        'title',
        'status',
        'reject_reason',
        'competitor',
        'region',
        'source',
    )
    search_fields = ('title', 'media_name', 'media_domain', 'url')
    search_help_text = 'Поиск по заголовку, СМИ, домену или ссылке'
    ordering = ('-id',)


@register(CategorizedEvent, sqlalchemy_sessionmaker=AsyncSessionLocal)
class CategorizedEventAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_PIPELINE
    verbose_name = 'Размеченное событие'
    verbose_name_plural = 'Разметка LLM (BP-3)'

    list_display = (
        'id',
        'normalized_item',
        'priority',
        'category',
        'tonality',
        'department',
        'deadline',
        'categorized_at',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'normalized_item': 'Событие',
        'priority': 'Приоритет',
        'category': 'Категория',
        'tonality': 'Тональность',
        'media_index': 'Медиаиндекс',
        'action': 'Требуемое действие',
        'deadline': 'Срок реакции',
        'department': 'Отдел',
        'comment': 'Комментарий',
        'llm_model': 'Модель LLM',
        'prompt_version': 'Версия промпта',
        'categorized_at': 'Размечено',
    }
    list_select_related = ('normalized_item', 'category', 'department')
    list_filter = (
        'normalized_item',
        'priority',
        'category',
        'tonality',
        'department',
    )
    search_fields = ('action', 'comment')
    search_help_text = 'Поиск по требуемому действию или комментарию'
    ordering = ('-id',)


@register(Alert, sqlalchemy_sessionmaker=AsyncSessionLocal)
class AlertAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_PIPELINE
    verbose_name = 'Уведомление'
    verbose_name_plural = 'Уведомления (BP-5)'

    list_display = (
        'id',
        'showcase_event',
        'event_type',
        'priority',
        'user',
        'channel',
        'mode',
        'status',
        'sent_at',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'showcase_event': 'Событие витрины',
        'event_type': 'Тип события',
        'priority': 'Приоритет',
        'user': 'Получатель',
        'channel': 'Канал',
        'mode': 'Режим доставки',
        'status': 'Статус',
        'error_message': 'Ошибка',
        'created_at': 'Создано',
        'sent_at': 'Отправлено',
    }
    list_select_related = (
        'showcase_event',
        'event_type',
        'user',
        'channel',
    )
    list_filter = (
        'showcase_event',
        'event_type',
        'status',
        'priority',
        'mode',
        'channel',
        'user',
    )
    search_fields = ('error_message',)
    search_help_text = 'Поиск по тексту ошибки доставки'
    ordering = ('-id',)


@register(SourceCandidate, sqlalchemy_sessionmaker=AsyncSessionLocal)
class SourceCandidateAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_PIPELINE
    verbose_name = 'Кандидат в источники'
    verbose_name_plural = 'Кандидаты (BP-7)'

    list_display = (
        'id',
        'domain',
        'competitor',
        'score',
        'status',
        'is_active',
        'created_at',
    )
    list_display_labels = {  # noqa: RUF012
        'id': 'Идентификатор',
        'domain': 'Домен-кандидат',
        'competitor': 'Конкурент',
        'url': 'Ссылка',
        'score': 'Оценка релевантности',
        'status': 'Статус переноса',
        'is_active': 'Рассматривается',
        'created_at': 'Предложен',
    }
    list_select_related = ('competitor',)
    list_filter = ('status', 'is_active', 'competitor')
    search_fields = ('domain', 'url')
    search_help_text = 'Поиск по домену или ссылке'
    ordering = ('-id',)
