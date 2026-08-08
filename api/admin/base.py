"""Базовые классы админки: сессия БД, права, названия разделов меню.

Чтобы не повторять одно и то же в двух десятках ModelAdmin:

- `db_session_maker` проставлен один раз на базовом классе. Для обычных
  моделей его дублирует `@register(..., sqlalchemy_sessionmaker=...)`
  (документированный путь), но инлайны через `register` не проходят —
  им класс-атрибут единственный способ получить сессию.
- Удаление выключено везде: все FK в проекте объявлены с
  `ondelete='RESTRICT'`, а конвенция проекта — мягкое выключение через
  `is_active` (см. core/database.py::ActiveMixin). Физический DELETE из
  админки всё равно упал бы ошибкой БД на первой же ссылке.
- `ReadOnlyModelAdmin` — для слоёв данных конвейера: их пишет пайплайн,
  руками их править нельзя (подробнее в докстрингах api/admin/pipeline.py).
"""

from typing import Any
from uuid import UUID

from fastadmin import SqlAlchemyInlineModelAdmin, SqlAlchemyModelAdmin
from fastadmin.models.schemas import ModelFieldWidgetSchema
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import SQLAlchemyError

from core.database import AsyncSessionLocal

EMPTY = '—'


class RelatedLabelMixin:
    """В списке показывает ИМЯ связанного объекта вместо его id.

    По умолчанию FastAdmin кладёт в колонку связи сырое значение FK
    (`competitor` → `53`): читать такой список невозможно. Подменяем
    значение на `__str__` связанного объекта — в колонке оказывается
    «АвтоМЛ».

    Почему не `@display`-метод (документированный путь библиотеки): при
    совпадении имени метода с именем поля модели FastAdmin рисует ДВЕ
    колонки — одну по полю (с фильтром и сортировкой), вторую по
    display-методу (см. fastadmin/models/helpers.py::generate_models_schema,
    два независимых цикла по одному и тому же `list_display`). Подмена на
    уровне сериализации оставляет ровно одну колонку — ту, у которой есть
    фильтр.

    Только для списка (`list_view=True`). На карточке записи связь должна
    остаться идентификатором: её принимает выпадающий список AsyncSelect,
    и строка вместо id сломала бы сохранение формы.

    Связь нужно перечислить в `list_select_related`, иначе на списке она не
    подгрузится. Экспорт же выгружает все поля модели, в том числе связи
    вне `list_select_related`, — у отсоединённого объекта чтение такой
    связи это исключение, поэтому мягко откатываемся к id вместо падения
    всей выгрузки.
    """

    async def serialize_obj_attributes(
        self,
        obj: Any,
        attributes_to_serizalize: list[ModelFieldWidgetSchema],
        list_view: bool = False,
    ) -> dict[str, Any]:
        serialized = await super().serialize_obj_attributes(
            obj, attributes_to_serizalize, list_view=list_view
        )
        if not list_view:
            return serialized
        for field in attributes_to_serizalize:
            # У связи имя поля и имя колонки расходятся: `competitor` против
            # `competitor_id`. У обычной колонки они совпадают.
            if field.column_name == field.name:
                continue
            serialized[field.name] = self._related_label(
                obj, field.name, serialized.get(field.name)
            )
        return serialized

    @staticmethod
    def _related_label(obj: Any, field_name: str, fk_value: Any) -> str:
        try:
            value = getattr(obj, field_name, None)
        except SQLAlchemyError:
            value = None
        if value is not None:
            return str(value)
        return str(fk_value) if fk_value is not None else EMPTY


# Разделы левого меню. FastAdmin поддерживает только один уровень
# вложенности (`menu_section` — строка), а ширина боковой панели
# фиксирована: длинные названия обрезаются многоточием. Поэтому названия
# короткие и различаются ПЕРВЫМ словом — «Администрирование · …» у трёх
# разделов подряд читалось одинаково и было бесполезно.
MENU_USERS = 'Пользователи'
MENU_SHOWCASE = 'Витрина'
MENU_ACTIONS = 'План действий'
MENU_ADMIN_PARSING = 'Настройки парсинга'
MENU_ADMIN_NORMALIZATION = 'Настройки валидации'
MENU_ADMIN_ALERTING = 'Настройки алертинга'
MENU_PIPELINE = 'Данные конвейера'
MENU_PIPELINE_CONTROL = 'Пайплайн'


class IntPrimaryKeyMixin:
    """Приводит id из URL к int перед обращением к БД.

    Обходит баг FastAdmin 0.10.0: в маршрутах `/api/retrieve/{model}/{id}`
    и `/api/change/{model}/{id}` параметр объявлен как `UUID | int | str`,
    и pydantic-union отдаёт «882» строкой. Дальше это уходит прямо в
    `session.get(model, '882')`, а asyncpg строг к типам и роняет запрос
    (`invalid input for query argument $1: '882'`) — то есть открыть и
    сохранить карточку любой записи было бы нельзя.

    Правим у себя, а не в пакете: у всех наших моделей первичный ключ —
    целочисленный `id` (core/database.py::Mixin), поэтому приведение
    безопасно; если PK вдруг окажется нечисловым, значение уходит как есть.
    """

    async def orm_get_obj(self, id: Any) -> Any | None:
        return await super().orm_get_obj(self._to_pk(id))

    async def orm_serialize_obj_by_id(self, id: Any) -> dict | None:
        return await super().orm_serialize_obj_by_id(self._to_pk(id))

    async def orm_save_obj(self, id: Any, payload: dict) -> Any:
        return await super().orm_save_obj(self._to_pk(id), payload)

    async def orm_delete_obj(self, id: Any) -> None:
        return await super().orm_delete_obj(self._to_pk(id))

    def _to_pk(self, id: Any) -> Any:
        if id is None or not isinstance(id, str):
            return id
        pk_name = self.get_model_pk_name(self.model_cls)
        pk_column = sa_inspect(self.model_cls).columns.get(pk_name)
        python_type = getattr(
            getattr(pk_column, 'type', None), 'python_type', None
        )
        if python_type is int and id.lstrip('-').isdigit():
            return int(id)
        return id


class KodikModelAdmin(
    IntPrimaryKeyMixin, RelatedLabelMixin, SqlAlchemyModelAdmin
):
    """Общий базовый класс всех моделей админки."""

    db_session_maker = AsyncSessionLocal

    list_per_page = 25

    async def has_delete_permission(
        self, user_id: UUID | int | None = None
    ) -> bool:
        """Физическое удаление запрещено — выключаем через `is_active`."""
        return False


class ReadOnlyModelAdmin(KodikModelAdmin):
    """Только просмотр: данные пишет конвейер, а не человек."""

    async def has_add_permission(
        self, user_id: UUID | int | None = None
    ) -> bool:
        return False

    async def has_change_permission(
        self, user_id: UUID | int | None = None
    ) -> bool:
        return False


class KodikInlineModelAdmin(
    IntPrimaryKeyMixin, RelatedLabelMixin, SqlAlchemyInlineModelAdmin
):
    """Базовый класс инлайнов (дочерние строки на странице родителя)."""

    db_session_maker = AsyncSessionLocal
