"""Модели BP-6 (план действий).

Единственная часть BP-6 с записью — таблица ActionItem. Остальное (дашборды,
карта рынка, паспорт конкурента) — DataLens, он только читает витрину.

- ActionItem: по событию П1/П2 человек заводит задачу, отдел меняет статус.
  Поля строго из ТЗ: задача → отдел → срок → ожидаемый результат → статус.

Nullability — только через аннотацию Mapped: Mapped[str] -> NOT NULL,
Mapped[str | None] -> NULL. Явный nullable= не дублируем.
"""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, Mixin
from core.enums import ActionStatus, action_status


class ActionItem(Base, Mixin):
    """План действий BP-6: задача по событию витрины.

    Заполняется человеком (аналитиком) через веб-форму/админку, не DataLens.
    Отделы меняют только статус (open → in_progress → done). DataLens читает
    эту таблицу для дашборда «план действий».
    """

    showcase_event_id: Mapped[int] = mapped_column(
        ForeignKey('showcase_event.id', ondelete='RESTRICT'),
        comment='По какому событию витрины заведена задача',
    )
    task: Mapped[str] = mapped_column(
        String(512),
        comment='Задача: что конкретно сделать (решение человека)',
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey('department.id', ondelete='RESTRICT'),
        comment='Ответственный отдел',
    )
    deadline: Mapped[date | None] = mapped_column(
        Date,
        comment='Срок',
    )
    expected_result: Mapped[str | None] = mapped_column(
        Text,
        comment='Ожидаемый результат',
    )
    status: Mapped[ActionStatus] = mapped_column(
        action_status,
        default=ActionStatus.open,
        server_default=text("'open'"),
        comment='Статус: open → in_progress → done. Меняют отделы',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Когда задача заведена',
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        server_default=func.now(),
        comment='Обновляется при смене статуса',
    )
