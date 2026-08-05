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

from fastadmin import SqlAlchemyInlineModelAdmin, SqlAlchemyModelAdmin, display
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import SQLAlchemyError

from core.database import AsyncSessionLocal

EMPTY = '—'


def related(field: str):
    """Колонка списка с ИМЕНЕМ связанного объекта вместо его id.

    По умолчанию FastAdmin отдаёт в список сырое значение FK-колонки
    (`competitor_id` → `53`): читать и тем более искать по такому списку
    невозможно. `@display`-метод получает сам объект и возвращает его
    `__str__`, поэтому в колонке оказывается «АвтоМЛ».

    Имя метода в классе должно совпадать с именем поля в `list_display` —
    тогда фильтр по колонке продолжает работать как выпадающий список
    (конфигурация фильтра берётся из поля модели, а не отсюда).

    Связь нужно перечислить в `list_select_related`, иначе на списке она
    не подгрузится. Но список — не единственный путь сюда: тот же объект
    сериализуется при входе в админку и на карточке записи, а там
    `list_select_related` не применяется и связь остаётся ленивой. У
    отсоединённого объекта это исключение, поэтому мягко откатываемся к id
    вместо падения всей страницы (в формах подпись всё равно подставляет
    выпадающий список на фронтенде).
    """

    @display
    async def _show_related(self, obj: Any) -> str:
        try:
            value = getattr(obj, field, None)
        except SQLAlchemyError:
            value = None
        if value is not None:
            return str(value)
        fk_value = getattr(obj, f'{field}_id', None)
        return str(fk_value) if fk_value is not None else EMPTY

    return _show_related


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


class KodikModelAdmin(IntPrimaryKeyMixin, SqlAlchemyModelAdmin):
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


class KodikInlineModelAdmin(IntPrimaryKeyMixin, SqlAlchemyInlineModelAdmin):
    """Базовый класс инлайнов (дочерние строки на странице родителя)."""

    db_session_maker = AsyncSessionLocal
