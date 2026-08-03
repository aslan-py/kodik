"""Валидатор `ShowcaseEventUpdate` (`api/schemas/showcase.py`)."""

from typing import Self


def require_at_least_one_field(schema: Self) -> Self:
    """Запрещает пустое тело PATCH /showcase/{id}.

    Без этого пустой `{}` тихо проходил бы валидацию и превращался в
    no-op в `ShowcaseCRUD.update()` (`exclude_unset=True` не находит
    изменений) — лучше явный 422, чем молчаливое ничего-не-случилось.
    """
    if not schema.model_fields_set:
        raise ValueError('Нужно передать хотя бы одно поле для обновления')
    return schema
