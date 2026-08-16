"""Админка проекта на FastAdmin. Монтируется в api/main.py на `/admin`.

Отдельного сервера и контейнера не нужно: это то же самое ASGI-приложение,
что и API (см. api/ADMIN_README.md).

ВАЖЕН ПОРЯДОК В ЭТОМ ФАЙЛЕ. FastAdmin читает свои настройки прямо из
`os.environ` в момент импорта `fastadmin.settings` (там обычные
`os.getenv(...)` на уровне класса). Наш `.env` разбирает pydantic-settings
в объект `core.config.settings` и в `os.environ` ничего не кладёт — значит
переменные нужно разложить руками ДО первого импорта fastadmin. Поэтому
здесь сначала идёт `_bootstrap_env()`, и только потом импорты пакета
(ruff E402 подавлен осознанно).

`setdefault`, а не присваивание: если переменная уже задана снаружи
(docker/CI), она главнее нашего `.env`.
"""

import os

from core.config import settings


def _bootstrap_env() -> None:
    """Разложить настройки админки в os.environ до импорта fastadmin."""
    secret = settings.admin_secret_key or settings.jwt_secret_key
    defaults = {
        # Должен совпадать с путём mount в api/main.py, иначе не найдётся
        # статика (/admin/static/...).
        'ADMIN_PREFIX': 'admin',
        'ADMIN_SITE_NAME': settings.admin_site_name,
        'ADMIN_LANGUAGE': settings.admin_language,
        'ADMIN_SECRET_KEY': secret,
        # Имя модели (и поля-логина), по которой FastAdmin ищет ModelAdmin
        # с методом authenticate — см. api/admin/users.py.
        'ADMIN_USER_MODEL': 'User',
        'ADMIN_USER_MODEL_USERNAME_FIELD': 'email',
        # По умолчанию в библиотеке True: кука сессии уходит только по
        # HTTPS, и на http://localhost вход молча не срабатывает.
        'ADMIN_SESSION_COOKIE_SECURE': str(
            settings.admin_session_cookie_secure
        ).lower(),
        'ADMIN_DATE_FORMAT': 'DD.MM.YYYY',
        'ADMIN_DATETIME_FORMAT': 'DD.MM.YYYY HH:mm',
    }
    for key, value in defaults.items():
        # Docker Compose passes ``ADMIN_SECRET_KEY=`` through as an existing,
        # but empty, environment variable.  Treat it like an omitted value so
        # the documented fallback to JWT_SECRET_KEY remains effective.
        if key == 'ADMIN_SECRET_KEY' and not os.environ.get(key):
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


_bootstrap_env()

from fastadmin import fastapi_app as fastadmin_app  # noqa: E402

# Импорт ради побочного эффекта: каждый модуль регистрирует свои ModelAdmin
# через @register, без этого админка окажется пустой. Порядок — алфавитный
# (ruff isort пересортирует любой другой), реальную позицию раздела
# «Пайплайн» в сайдбаре смотрим по факту (см. design.md изменения
# add-pipeline-reparse-and-admin-ui, Open Questions).
from api.admin import (  # noqa: E402, F401
    alerting,
    normalization,
    parsing,
    pipeline,
    pipeline_control,
    pipeline_runs,
    users,
    workflow,
)
from api.admin.app import create_admin_app  # noqa: E402
from api.admin.navigation import configure_admin_navigation  # noqa: E402

configure_admin_navigation()
admin_app = create_admin_app(fastadmin_app)

__all__ = ['admin_app']
