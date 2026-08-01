"""Модели BP-1 (слой сбора данных).

Содержит справочники и таблицы для конфигурации и хранения результатов
парсинга:

- Trigger: ключевые слова для поиска
- Competitor: конкуренты, которых мониторим
- Source: источники данных (сайты/ресурсы)
- SearchTask: матрица конфигурации (кто, где, что ищет)
- RawItem: центральное хранилище сырых результатов парсинга

Все модели наследуют Mixin (id + имя таблицы). Справочники (Trigger,
Competitor, Source) и SearchTask наследуют ActiveMixin (флаг is_active).
У SearchTask is_active означает «активна ли задача для Celery Beat».
RawItem ActiveMixin не использует — вместо флага у него поле status.

Nullability берётся из аннотации Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import ActiveMixin, Base, Mixin
from core.enums import RawItemStatus, raw_item_status


class Trigger(Base, Mixin, ActiveMixin):
    """Справочник триггеров (ключевые слова для поиска).

    Содержит ключевые слова, которые парсер использует для поиска
    информации о конкурентах на источниках. Один триггер может
    применяться к разным комбинациям конкурент-источник через
    SearchTask.
    """

    keyword: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        comment=(
            'Само поисковое слово/навык (например, Юрист, Python, Django, Суд)'
        ),
    )


class Competitor(Base, Mixin, ActiveMixin):
    """Справочник конкурентов.

    Хранит названия компаний, которых мы мониторим.
    Может содержать ИНН для поиска в государственных реестрах.
    """

    name: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        comment='Название компании (например, Бегемот, Рога и Копыта)',
    )
    inn: Mapped[str | None] = mapped_column(
        String(12),
        unique=True,
        comment='ИНН конкурента (опционально, поиск по гос-реестрам)',
    )


class Source(Base, Mixin, ActiveMixin):
    """Справочник источников данных.

    Содержит адреса сайтов и ресурсов, на которых парсер ищет
    информацию о конкурентах (вакансии, новости, тендеры и т.д.).
    """

    name: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        comment='Имя сайта/ресурса (например, hh.ru, авито, суд_реестр)',
    )


class SearchTask(Base, Mixin, ActiveMixin):
    """Матрица задач парсинга.

    Служебная таблица конфигурации: связывает конкурента, источник и
    триггер. На неё опирается Celery Beat при формировании очереди
    задач. id строки используется как ключ в Redis для отслеживания
    последнего хэша.

    is_active (из ActiveMixin) здесь = «активна ли задача для Celery Beat»:
    Beat берёт в перебор только активные строки.
    """

    competitor_id: Mapped[int] = mapped_column(
        ForeignKey('competitor.id', ondelete='RESTRICT'),
        comment='Какого конкурента ищем',
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey('source.id', ondelete='RESTRICT'),
        comment='На каком источнике ищем',
    )
    trigger_id: Mapped[int | None] = mapped_column(
        ForeignKey('trigger.id', ondelete='RESTRICT'),
        comment=(
            'По какому слову ищем (опционально, NULL = парсим источник в лоб)'
        ),
    )

    __table_args__ = (
        # Ловит дубли задач с ЗАДАННЫМ триггером (trigger_id NOT NULL).
        UniqueConstraint(
            'competitor_id',
            'source_id',
            'trigger_id',
            name='uq_search_task_config',
        ),
        # Ловит дубли задач БЕЗ триггера (trigger_id IS NULL): обычный UNIQUE
        # их не видит, т.к. в Postgres NULL != NULL. Partial unique index
        # закрывает именно этот случай.
        Index(
            'uq_search_task_no_trigger',
            'competitor_id',
            'source_id',
            unique=True,
            postgresql_where=text('trigger_id IS NULL'),
        ),
    )

    # Relationships для удобного доступа к связанным данным
    competitor: Mapped['Competitor'] = relationship(
        'Competitor',
        backref='search_tasks',
        lazy='selectin',
    )
    source: Mapped['Source'] = relationship(
        'Source',
        backref='search_tasks',
        lazy='selectin',
    )
    trigger: Mapped['Trigger | None'] = relationship(
        'Trigger',
        backref='search_tasks',
        lazy='selectin',
    )


class RawItem(Base, Mixin):
    """Центральное хранилище сырых материалов (BP-1).

    Хранит результаты парсинга: метаданные (search_task_id), статус
    обработки, сам контент (raw_data как JSON), путь к HTML на диске
    и техническую информацию об ошибках. new/changed добавляют новую
    строку (история версий); при совпадении хэша строку НЕ создаём и статус
    НЕ трогаем, обновляем только updated_at; error пишет строку с пустым
    контентом и error_message.
    """

    search_task_id: Mapped[int] = mapped_column(
        ForeignKey('search_task.id', ondelete='RESTRICT'),
        comment=(
            'Ссылка на задачу конфигурации. Через неё вытягиваем '
            'конкурента, источник и триггер'
        ),
    )
    status: Mapped[RawItemStatus] = mapped_column(
        raw_item_status,
        default=RawItemStatus.new,
        server_default=text("'new'"),
        comment=(
            'new/changed = новая строка; error = сбой сбора. '
            'При совпадении хэша строку не создаём, статус не трогаем'
        ),
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        comment=(
            'Хэш от JSON контента для сверки через Redis. NULL при status=error'
        ),
    )
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB,
        comment=(
            'Сырой извлечённый контент страницы в формате JSON. '
            'NULL при status=error'
        ),
    )
    html_file_path: Mapped[str | None] = mapped_column(
        String(512),
        comment=(
            'Путь к сохранённому слепку HTML на диске/S3 для '
            'истории. NULL при status=error'
        ),
    )
    source_request_url: Mapped[str | None] = mapped_column(
        String(512),
        comment=(
            'Ссылка на оригинальный веб-запрос парсера. NULL при ранней ошибке'
        ),
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        comment='Текст ошибки при status=error. NULL для успешных',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Время первой фиксации этого снимка в системе',
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment=(
            'Время последней СВЕРКИ. При совпадении хэша обновляем '
            'ТОЛЬКО это поле (статус не трогаем)'
        ),
    )
