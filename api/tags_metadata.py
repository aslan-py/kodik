"""Порядок и описания тегов для Swagger (`FastAPI(openapi_tags=...)`)."""

tags_metadata = [
    {
        'name': 'Аутентификация',
        'description': 'Регистрация и логин, выдача JWT',
    },
    {
        'name': 'Пользователи',
        'description': (
            'Профиль текущего пользователя, список пользователей, '
            'подтверждение роли (pending → viewer/analyst/admin)'
        ),
    },
    {
        'name': 'Витрина',
        'description': 'Чтение и правка витрины BP-4 (showcase_event)',
    },
]
