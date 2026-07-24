"""Конфигурация SQLAlchemy для асинхронной работы с Postgres.

Содержит:
- Base: базовый класс для всех моделей (подключается к Alembic для миграций)
- Mixin: примесь для автоматического имени таблицы и id
- ActiveMixin: примесь с флагом is_active (для справочников)
- engine: асинхронный engine (пул соединений)
- AsyncSessionLocal: фабрика сессий
- get_async_session: генератор сессий для использования в парсерах/воркерах

Используется парсерами, Celery-тасками, скриптами напрямую.
FastAPI-обвязка (Depends) добавляется отдельно в api/deps.py.
"""
import re
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from core.config import settings


class Mixin:
    """Добавляет автоматическое имя таблицы и id (primary key).

    Имя таблицы генерируется из CamelCase в snake_case:
    SearchTask -> search_task, RawItem -> raw_item.

    sort_order=-1 ставит id первой колонкой таблицы (иначе колонки миксина
    оказываются после колонок модели).
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__)
        return name.lower()

    id: Mapped[int] = mapped_column(primary_key=True, sort_order=-1)
    # id: Mapped[int] = mapped_column(primary_key=True, sort_order=-1)


class ActiveMixin:
    """Добавляет флаг is_active.

    Используется для справочников, где записи нужно мягко выключать
    (не участвует в парсинге/выборках), не удаляя физически из БД.

    server_default=true() — дефолт на уровне БД, чтобы INSERT в обход ORM
    (сидинг в миграции, админка, сырой SQL) не падал на NOT NULL.
    """

    is_active: Mapped[bool] = mapped_column(
        default=True,
        server_default=text('true'),
        comment='Мягкое выключение записи: не участвует в выборках, из БД не удаляем',
    )


class Base(DeclarativeBase):
    """Базовый класс для моделей."""


engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Асинхронный генератор сессий.

    Используется напрямую (парсеры, Celery-таски, скрипты) через
    `async with AsyncSessionLocal() as session:` или через этот генератор.
    FastAPI-обвязка (Depends) сюда не добавляется — она появится отдельным
    модулем в api/deps.py, когда будут писаться эндпоинты.
    """
    async with AsyncSessionLocal() as async_session:
        try:
            yield async_session
        except Exception:
            await async_session.rollback()
            raise
        finally:
            await async_session.close()
