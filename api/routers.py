"""Единая точка сборки роутеров: префиксы и теги назначаются здесь, а не
внутри `api/endpoints/*.py`.

`endpoints/*.py` содержат только сами эндпоинты (`APIRouter()` без prefix/
tags) — так вся карта API (какой префикс/тег у какого модуля) видна в
одном месте, не открывая каждый файл по отдельности.
"""

from fastapi import APIRouter

from api.endpoints import (
    action_items_router,
    auth_router,
    showcase_router,
    users_router,
)

main_router = APIRouter()

main_router.include_router(auth_router, prefix='/auth', tags=['Аутентификация'])
main_router.include_router(users_router, prefix='/users', tags=['Пользователи'])
main_router.include_router(
    showcase_router, prefix='/showcase', tags=['Витрина']
)
main_router.include_router(
    action_items_router, prefix='/action-items', tags=['План действий']
)
