"""Модель-маркер для админки раннера этапов.

`PipelineControlMarker` не хранит данных — в таблице никогда не будет ни
одной строки. Единственная причина существования: FastAdmin `@register()`
требует настоящую SQLAlchemy-модель, чтобы прицепить к ней кнопки запуска
этапов (`@widget_action`, см. api/admin/pipeline_control.py) — виджетов
самих по себе, без модели-хозяина, библиотека не поддерживает.
"""

from core.database import Base, Mixin


class PipelineControlMarker(Base, Mixin):
    """Пустой якорь для страницы «Пайплайн» в админке. Данных не хранит."""

    def __str__(self) -> str:
        return 'Управление пайплайном'
