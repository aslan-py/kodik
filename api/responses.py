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

# ============================================================================
#  Составы под конкретные эндпоинты (api/endpoints/*.py)
# ============================================================================

REGISTER_RESPONSES = {**CONFLICT_RESPONSE, **NOT_FOUND_RESPONSE}
LOGIN_RESPONSES = {**INVALID_CREDENTIALS_RESPONSE}
ME_RESPONSES = {**UNAUTHORIZED_RESPONSE}
USERS_LIST_RESPONSES = {**UNAUTHORIZED_RESPONSE, **FORBIDDEN_RESPONSE}
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
