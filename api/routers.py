"""Единая точка сборки роутеров: префиксы и теги назначаются здесь, а не
внутри `api/endpoints/*.py`.

`endpoints/*.py` содержат только сами эндпоинты (`APIRouter()` без prefix/
tags) — так вся карта API (какой префикс/тег у какого модуля) видна в
одном месте, не открывая каждый файл по отдельности.
"""

from fastapi import APIRouter

from api.endpoints import (
    action_items_router,
    alert_router,
    auth_router,
    black_domain_router,
    categorized_event_router,
    category_router,
    channel_router,
    competitor_router,
    department_router,
    event_type_router,
    normalized_item_router,
    raw_item_router,
    region_router,
    routing_rule_router,
    search_task_router,
    showcase_router,
    source_candidate_router,
    source_router,
    stop_word_router,
    topic_limit_router,
    trigger_router,
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

# --- Администрирование (парсинг, BP-1) ---
_ADMIN_PARSING = 'Администрирование (парсинг)'
main_router.include_router(
    competitor_router, prefix='/competitors', tags=[_ADMIN_PARSING]
)
main_router.include_router(
    source_router, prefix='/sources', tags=[_ADMIN_PARSING]
)
main_router.include_router(
    trigger_router, prefix='/triggers', tags=[_ADMIN_PARSING]
)
main_router.include_router(
    search_task_router, prefix='/search-tasks', tags=[_ADMIN_PARSING]
)

# --- Администрирование (нормализация, BP-2/BP-3) ---
_ADMIN_NORMALIZATION = 'Администрирование (нормализация)'
main_router.include_router(
    region_router, prefix='/regions', tags=[_ADMIN_NORMALIZATION]
)
main_router.include_router(
    black_domain_router,
    prefix='/black-domains',
    tags=[_ADMIN_NORMALIZATION],
)
main_router.include_router(
    stop_word_router, prefix='/stop-words', tags=[_ADMIN_NORMALIZATION]
)
main_router.include_router(
    topic_limit_router, prefix='/topic-limits', tags=[_ADMIN_NORMALIZATION]
)
main_router.include_router(
    category_router, prefix='/categories', tags=[_ADMIN_NORMALIZATION]
)
main_router.include_router(
    department_router, prefix='/departments', tags=[_ADMIN_NORMALIZATION]
)

# --- Администрирование (настройки алертинга, BP-5) ---
_ADMIN_ALERTING = 'Администрирование (настройки алертинга)'
main_router.include_router(
    event_type_router, prefix='/event-types', tags=[_ADMIN_ALERTING]
)
main_router.include_router(
    channel_router, prefix='/channels', tags=[_ADMIN_ALERTING]
)
main_router.include_router(
    routing_rule_router, prefix='/routing-rules', tags=[_ADMIN_ALERTING]
)

# --- Read-only просмотр данных пайплайна (FASTAPI_PLAN.md, раздел 6) ---
main_router.include_router(
    raw_item_router,
    prefix='/raw-items',
    tags=['Данные после парсинга (BP-1)'],
)
main_router.include_router(
    normalized_item_router,
    prefix='/normalized-items',
    tags=['Данные после нормализации (BP-2)'],
)
main_router.include_router(
    categorized_event_router,
    prefix='/categorized-events',
    tags=['Данные после проработки LLM (BP-3)'],
)
main_router.include_router(
    alert_router,
    prefix='/alerts',
    tags=['Отправленные уведомления (BP-5)'],
)

# --- BP-7: кандидаты в источники (только просмотр) ---
main_router.include_router(
    source_candidate_router,
    prefix='/source-candidates',
    tags=['Источники — кандидаты (BP-7)'],
)
