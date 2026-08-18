"""Сборка FastAPI-приложения: FastAPI() + include_router + админка.

Никакой пайплайн-логики здесь нет и не будет — оркестрация BP-2/BP-4/BP-5
остаётся задачей Celery+Beat, отдельным процессом (FASTAPI_PLAN.md, п.5).

Админка (FastAdmin) монтируется сюда же, отдельного сервера/контейнера не
требует: один процесс отдаёт и JSON API, и веб-интерфейс на /admin.
Инструкция — api/ADMIN_README.md.

Запуск: python -m api.main
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Регистрирует ВСЕ модели в Base.metadata: без этого SQLAlchemy не резолвит
# FK на таблицы модулей, которые роутеры не импортируют напрямую (напр.
# categorized_event -> normalized_item), и flush падает с
# NoReferencedTableError. Тот же приём в alembic/env.py.
import src.db_registry  # noqa: F401
from api.admin import admin_app
from api.routers import main_router
from api.tags_metadata import tags_metadata
from core.config import settings

app = FastAPI(
    title=settings.app_title,
    description=settings.description,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(main_router)

# Путь обязан совпадать с ADMIN_PREFIX (api/admin/__init__.py) — по нему
# фронтенд админки запрашивает свою статику.
app.mount('/admin', admin_app)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'api.main:app',
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
