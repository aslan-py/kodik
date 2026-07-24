"""Центральный реестр всех моделей проекта.

Импортируется в alembic/env.py — регистрирует все модели в Base.metadata,
что необходимо для autogenerate миграций.

При добавлении нового BP — добавить одну строку импорта сюда.
env.py трогать не нужно.
"""
import src.bp1  # noqa: F401 — Trigger, Competitor, Source, SearchTask, RawItem
# import src.bp2  # noqa: F401 — добавить когда появятся модели bp2
# import src.bp3  # noqa: F401
# import src.bp4  # noqa: F401
# import src.bp5  # noqa: F401
# import src.bp6  # noqa: F401
# import src.bp7  # noqa: F401
