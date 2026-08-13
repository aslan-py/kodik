"""Пресеты `responses={...}` — документируют в Swagger ошибки, которые
эндпоинт может вернуть вручную (`HTTPException`).

FastAPI сам добавляет в схему описание только для 200 (успех) и 422
(валидация тела/query) — остальные статусы Swagger по умолчанию вообще не
показывает, хотя эндпоинт их реально бросает (401/403/404/409). Формат
ответа не менялся: `ErrorDetail` (`api/schemas/error.py`) описывает
стандартный `{"detail": "..."}` FastAPI, кастомных exception-хэндлеров нет.
"""

from typing import Any

from fastapi import status

from api.schemas.error import ErrorDetail


def _response(description: str) -> dict[str, Any]:
    return {'description': description, 'model': ErrorDetail}


UNAUTHORIZED_RESPONSE = {
    status.HTTP_401_UNAUTHORIZED: _response(
        'Токен не передан, невалиден или просрочен'
    ),
}
FORBIDDEN_RESPONSE = {
    status.HTTP_403_FORBIDDEN: _response(
        'Роль пользователя не даёт доступа к этому действию'
    ),
}
NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: _response('Ресурс не найден'),
}
CONFLICT_RESPONSE = {
    status.HTTP_409_CONFLICT: _response(
        'Email или telegram_id уже заняты другим пользователем'
    ),
}
INVALID_CREDENTIALS_RESPONSE = {
    status.HTTP_401_UNAUTHORIZED: _response('Неверный email или пароль'),
}
INVALID_RESET_CODE_RESPONSE = {
    status.HTTP_400_BAD_REQUEST: _response(
        'Код сброса пароля неверен, истёк или исчерпаны попытки'
    ),
}
CURRENT_PASSWORD_RESPONSE = {
    status.HTTP_401_UNAUTHORIZED: _response(
        'Токен не передан/невалиден, либо current_password не совпадает '
        'при смене email/пароля'
    ),
}
ACTION_ITEM_CONFLICT_RESPONSE = {
    status.HTTP_409_CONFLICT: _response(
        'assigned_user_id не состоит в указанном department_id'
    ),
}
REFERENCE_CONFLICT_RESPONSE = {
    status.HTTP_409_CONFLICT: _response(
        'Значение уже занято (нарушение unique/UniqueConstraint)'
    ),
}

# ============================================================================
#  Составы под конкретные эндпоинты (api/endpoints/*.py)
# ============================================================================

REGISTER_RESPONSES = {**CONFLICT_RESPONSE, **NOT_FOUND_RESPONSE}
LOGIN_RESPONSES = {**INVALID_CREDENTIALS_RESPONSE}
LOGOUT_RESPONSES = {**UNAUTHORIZED_RESPONSE}
PASSWORD_RESET_CONFIRM_RESPONSES = {**INVALID_RESET_CODE_RESPONSE}
ME_RESPONSES = {**UNAUTHORIZED_RESPONSE}
ME_UPDATE_RESPONSES = {
    **CURRENT_PASSWORD_RESPONSE,
    **CONFLICT_RESPONSE,
    **NOT_FOUND_RESPONSE,
}
USERS_LIST_RESPONSES = {**UNAUTHORIZED_RESPONSE, **FORBIDDEN_RESPONSE}
USER_DETAIL_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
}
USER_ROLE_UPDATE_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
}
SHOWCASE_LIST_RESPONSES = {**UNAUTHORIZED_RESPONSE, **FORBIDDEN_RESPONSE}
SHOWCASE_DETAIL_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
}
ACTION_ITEM_LIST_RESPONSES = {**UNAUTHORIZED_RESPONSE, **FORBIDDEN_RESPONSE}
ACTION_ITEM_DETAIL_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
}
ACTION_ITEM_CREATE_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
    **ACTION_ITEM_CONFLICT_RESPONSE,
}
ACTION_ITEM_UPDATE_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
    **ACTION_ITEM_CONFLICT_RESPONSE,
}

# --- Справочники (api/endpoints/reference.py) и read-only просмотр
# пайплайна (raw_item/normalized_item/categorized_event/alert) — обе группы
# используют один и тот же набор: EditorDep везде (см. api/FASTAPI_PLAN.md,
# раздел 6), различается только наличие 409 у мутаций.
REFERENCE_LIST_RESPONSES = {**UNAUTHORIZED_RESPONSE, **FORBIDDEN_RESPONSE}
REFERENCE_DETAIL_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
}
REFERENCE_WRITE_RESPONSES = {
    **UNAUTHORIZED_RESPONSE,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
    **REFERENCE_CONFLICT_RESPONSE,
}

# --- department: GET публичный (без токена), см. api/endpoints/department.py
PUBLIC_LIST_RESPONSES: dict[int, dict[str, Any]] = {}
PUBLIC_DETAIL_RESPONSES = {**NOT_FOUND_RESPONSE}
