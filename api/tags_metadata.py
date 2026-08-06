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
    {
        'name': 'План действий',
        'description': (
            'BP-6: задачи по событиям витрины (action_item). Создание — '
            'analyst/admin. Чтение/смена статуса — viewer тоже, но только '
            'в рамках своего отдела'
        ),
    },
    {
        'name': 'Администрирование (парсинг)',
        'description': (
            'CRUD над справочниками сбора данных BP-1: competitor, source, '
            'trigger, search_task. Доступ — analyst/admin. Удаление — '
            'мягкое (`is_active=false`)'
        ),
    },
    {
        'name': 'Администрирование (нормализация)',
        'description': (
            'CRUD над справочниками очистки/разметки BP-2/BP-3: region, '
            'black_domain, stop_word, topic_limit, category, department. '
            'Доступ — analyst/admin, кроме чтения `department` — оно '
            'публичное (нужно форме регистрации и профилю pending-'
            'пользователя до логина). Удаление — мягкое (`is_active=false`), '
            'кроме region (статический справочник городов, без флага)'
        ),
    },
    {
        'name': 'Администрирование (настройки алертинга)',
        'description': (
            'CRUD над справочниками маршрутизации алертов BP-5: '
            'event_type, channel, routing_rule. Доступ — analyst/admin. '
            'Удаление — мягкое (`is_active=false`)'
        ),
    },
    {
        'name': 'Данные после парсинга (BP-1)',
        'description': (
            'Только просмотр: raw_item — сырые результаты парсинга. '
            'Доступ — analyst/admin'
        ),
    },
    {
        'name': 'Данные после нормализации (BP-2)',
        'description': (
            'Только просмотр: normalized_item — очищенные и '
            'дедуплицированные события (silver-слой). Доступ — analyst/admin'
        ),
    },
    {
        'name': 'Данные после проработки LLM (BP-3)',
        'description': (
            'Только просмотр: categorized_event — размеченные события '
            '(gold-слой). Правка разметки — через `PATCH /showcase/{id}`, '
            'не здесь. Доступ — analyst/admin'
        ),
    },
    {
        'name': 'Отправленные уведомления (BP-5)',
        'description': (
            'Только просмотр: alert — неизменяемый журнал доставки '
            'алертов. Доступ — analyst/admin'
        ),
    },
    {
        'name': 'Источники — кандидаты (BP-7)',
        'description': (
            'Только просмотр: source_candidate — кандидаты в источники, '
            'предложенные агентом расширения (следующая итерация) и их '
            'перенос в source по порогу score (`SourceCandidatePromoter`, '
            'см. `src/bp7/BP7_README.md`). Доступ — analyst/admin'
        ),
    },
]
