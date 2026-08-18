"""Раздел «Пайплайн» — кнопки запуска этапов конвейера прямо из админки.

Каждая кнопка дёргает `core.pipeline.runner` — не дублирует его логику
(preflight, сводка, пометка заглушек), только вызывает и форматирует
результат. Host-модель — `PipelineControlMarker` (core/pipeline/models.py),
пустая, без данных: FastAdmin `@register()` требует настоящую ORM-модель,
чтобы прицепить `@widget_action` (см. design.md изменения
add-pipeline-reparse-and-admin-ui).

Заголовки кнопок берутся из `core.pipeline.registry.STAGES`, а не
дублируются здесь строками — так название этапа не может разъехаться
между реестром и админкой.
"""

from fastadmin import (
    WidgetActionArgumentProps,
    WidgetActionInputSchema,
    WidgetActionProps,
    WidgetActionResponseSchema,
    WidgetActionType,
    WidgetType,
    register,
    widget_action,
)

from api.admin.base import MENU_PIPELINE_CONTROL, ReadOnlyModelAdmin
from core.config import settings
from core.database import AsyncSessionLocal
from core.enums import PipelineRunKind, PipelineRunSource
from core.pipeline.models import PipelineControlMarker, PipelineSchedule
from core.pipeline.registry import STAGES
from core.pipeline.schedule import (
    InvalidPipelineSchedule,
    get_effective_schedule,
    validate_schedule_values,
)
from core.pipeline.service import PipelineRunConflict, PipelineRunService

REPARSE_FIELD = 'пересобрать'
TRUE_PARSING_FIELD = 'реальный сбор'
SCHEDULE_ENABLED_FIELD = 'включено'
SCHEDULE_CRON_FIELD = 'cron'
SCHEDULE_TIMEZONE_FIELD = 'часовой пояс'


def _reparse_requested(payload: WidgetActionInputSchema) -> bool:
    """Значение переключателя «пересобрать», если он вообще есть у кнопки.

    У кнопок без такого аргумента `payload.query` пуст — безопасный no-op.
    """
    for item in payload.query:
        if item.field_name == REPARSE_FIELD:
            return bool(item.value)
    return False


def _true_parsing_requested(
    payload: WidgetActionInputSchema,
) -> bool | None:
    """Значение переключателя «реальный сбор», если он есть у кнопки.

    `None` — у кнопки нет такого аргумента (все этапы, кроме первого):
    `run_stage()` тогда берёт `settings.true_parsing`, поведение как из
    CLI/Celery без явного переопределения. Если аргумент есть — значение
    из payload явно приводится к `bool` (тот же приём, что и у
    `_reparse_requested`: FastAdmin/Antd Switch иначе кладёт в payload не
    примитив, см. комментарий у `stage_1`).
    """
    for item in payload.query:
        if item.field_name == TRUE_PARSING_FIELD:
            return bool(item.value)
    return None


def _payload_value(
    payload: WidgetActionInputSchema, field_name: str, default: object
) -> object:
    for item in payload.query:
        if item.field_name == field_name:
            return item.value
    return default


async def _schedule_response() -> WidgetActionResponseSchema:
    async with AsyncSessionLocal() as session:
        effective = await get_effective_schedule(session)
    return WidgetActionResponseSchema(
        data=[
            {
                'enabled': effective.enabled,
                'cron': effective.cron,
                'timezone': effective.timezone,
                'enabled_source': effective.enabled_source,
                'cron_source': effective.cron_source,
                'timezone_source': effective.timezone_source,
                'next_run_at': effective.next_slot.isoformat(),
            }
        ]
    )


async def _run_stage_widget(
    number: int, payload: WidgetActionInputSchema
) -> WidgetActionResponseSchema:
    reparse = _reparse_requested(payload)
    true_parsing = _true_parsing_requested(payload)
    try:
        async with AsyncSessionLocal() as session:
            created = await PipelineRunService(session).enqueue_run(
                kind=PipelineRunKind.single,
                stage=number,
                source=PipelineRunSource.admin,
                parameters={
                    'reparse': reparse,
                    'true_parsing': true_parsing,
                },
            )
    except PipelineRunConflict as exc:
        return WidgetActionResponseSchema(
            data=[
                {
                    'status': 'conflict',
                    'run_id': str(exc.run_id),
                    'details_url': f'/pipeline/runs/{exc.run_id}',
                }
            ]
        )
    return WidgetActionResponseSchema(
        data=[
            {
                'status': 'queued',
                'run_id': str(created.run_id),
                'details_url': f'/pipeline/runs/{created.run_id}',
            }
        ]
    )


@register(PipelineControlMarker, sqlalchemy_sessionmaker=AsyncSessionLocal)
class PipelineControlAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_PIPELINE_CONTROL
    verbose_name = 'Пайплайн'
    verbose_name_plural = 'Пайплайн'

    widget_actions = (
        'show_technical_logs',
        'show_schedule',
        'save_schedule',
        'reset_schedule',
        'stage_1',
        'stage_2',
        'stage_3',
        'stage_4',
        'stage_5',
        'stage_6',
        'stage_7',
        'run_all_stages',
    )

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title='Технические логи (Grafana)',
        widget_action_type=WidgetActionType.Action,
    )
    async def show_technical_logs(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return WidgetActionResponseSchema(
            data=[
                {
                    'url': settings.grafana_url,
                    'hint': 'Откройте Grafana и найдите run_id из  запуска.',
                }
            ]
        )

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title='Расписание: показать',
        widget_action_type=WidgetActionType.Action,
    )
    async def show_schedule(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _schedule_response()

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title='Расписание: сохранить',
        widget_action_type=WidgetActionType.Action,
        widget_action_props=WidgetActionProps(
            arguments=[
                WidgetActionArgumentProps(
                    name=SCHEDULE_ENABLED_FIELD,
                    widget_type=WidgetType.Switch,
                    widget_props={
                        'defaultChecked': settings.pipeline_schedule_enabled
                    },
                ),
                WidgetActionArgumentProps(
                    name=SCHEDULE_CRON_FIELD,
                    widget_type=WidgetType.Input,
                    widget_props={
                        'defaultValue': settings.pipeline_schedule_cron
                    },
                ),
                WidgetActionArgumentProps(
                    name=SCHEDULE_TIMEZONE_FIELD,
                    widget_type=WidgetType.Input,
                    widget_props={
                        'defaultValue': settings.pipeline_schedule_timezone
                    },
                ),
            ]
        ),
    )
    async def save_schedule(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        enabled = bool(
            _payload_value(
                payload,
                SCHEDULE_ENABLED_FIELD,
                settings.pipeline_schedule_enabled,
            )
        )
        cron = str(
            _payload_value(
                payload, SCHEDULE_CRON_FIELD, settings.pipeline_schedule_cron
            )
        )
        timezone = str(
            _payload_value(
                payload,
                SCHEDULE_TIMEZONE_FIELD,
                settings.pipeline_schedule_timezone,
            )
        )
        try:
            validate_schedule_values(cron, timezone)
        except InvalidPipelineSchedule as exc:
            return WidgetActionResponseSchema(
                data=[{'status': 'invalid', 'error': str(exc)}]
            )
        async with AsyncSessionLocal() as session:
            schedule = await session.get(PipelineSchedule, 1)
            if schedule is None:
                return WidgetActionResponseSchema(
                    data=[{'status': 'unavailable'}]
                )
            schedule.enabled_override = enabled
            schedule.cron_override = cron
            schedule.timezone_override = timezone
            await session.commit()
        return await _schedule_response()

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title='Расписание: сбросить к .env',
        widget_action_type=WidgetActionType.Action,
    )
    async def reset_schedule(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        async with AsyncSessionLocal() as session:
            schedule = await session.get(PipelineSchedule, 1)
            if schedule is None:
                return WidgetActionResponseSchema(
                    data=[{'status': 'unavailable'}]
                )
            schedule.enabled_override = None
            schedule.cron_override = None
            schedule.timezone_override = None
            await session.commit()
        return await _schedule_response()

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title=f'Этап 1 — {STAGES[1].title}',
        widget_action_type=WidgetActionType.Action,
        # Переключатель реализации: выключен -> заглушка, включён ->
        # настоящий адаптивный сбор. Начальное положение отражает
        # settings.true_parsing, чтобы нажатие кнопки БЕЗ прикосновения к
        # переключателю давало то же поведение, что запуск из CLI/Celery
        # без явного переопределения.
        #
        # WidgetType.Switch, а не Checkbox — та же ловушка FastAdmin 0.10.0,
        # что и у переключателя «пересобрать» этапа 2 (см. комментарий там):
        # Checkbox кладёт в состояние событие onChange, а не bool.
        widget_action_props=WidgetActionProps(
            arguments=[
                WidgetActionArgumentProps(
                    name=TRUE_PARSING_FIELD,
                    widget_type=WidgetType.Switch,
                    widget_props={'defaultChecked': settings.true_parsing},
                ),
            ],
        ),
    )
    async def stage_1(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _run_stage_widget(1, payload)

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title=f'Этап 2 — {STAGES[2].title}',
        widget_action_type=WidgetActionType.Action,
        # Для Action-виджетов интерактивные поля формы задаются через
        # widget_action_props.arguments — НЕ через widget_action_filters
        # (тот механизм — для Chart-виджетов, фильтрует данные графика,
        # к полю ввода перед запуском действия отношения не имеет).
        #
        # WidgetType.Switch, а не Checkbox: в FastAdmin 0.10.0 у Action-формы
        # общий onChange для всех не-текстовых полей ожидает, что обработчик
        # получает готовое значение (`onChange(value)`), как у Switch/Select.
        # Antd Checkbox же передаёт туда событие (`onChange(event)`, булево —
        # в `event.target.checked`), для которого в FastAdmin отдельного
        # разбора нет — в итоге в состояние попадает объект события, а не
        # true/false, и переключатель либо не реагирует, либо срабатывает
        # непредсказуемо. Ловушка библиотеки, правим у себя (см. так же
        # api/admin/base.py — уже есть похожие обходы багов FastAdmin 0.10.0).
        #
        # Имя аргумента — сразу по-русски: подпись поля берётся FastAdmin из
        # технического имени (widget_props.label на неё не влияет), отдельного
        # перевода для произвольных полей библиотека не подхватывает.
        widget_action_props=WidgetActionProps(
            arguments=[
                WidgetActionArgumentProps(
                    name=REPARSE_FIELD,
                    widget_type=WidgetType.Switch,
                ),
            ],
        ),
    )
    async def stage_2(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _run_stage_widget(2, payload)

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title=f'Этап 3 — {STAGES[3].title}',
        widget_action_type=WidgetActionType.Action,
    )
    async def stage_3(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _run_stage_widget(3, payload)

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title=f'Этап 4 — {STAGES[4].title}',
        widget_action_type=WidgetActionType.Action,
    )
    async def stage_4(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _run_stage_widget(4, payload)

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title=f'Этап 5 — {STAGES[5].title}',
        widget_action_type=WidgetActionType.Action,
    )
    async def stage_5(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _run_stage_widget(5, payload)

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title=f'Этап 6 — {STAGES[6].title}',
        widget_action_type=WidgetActionType.Action,
    )
    async def stage_6(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _run_stage_widget(6, payload)

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title=f'Этап 7 — {STAGES[7].title}',
        widget_action_type=WidgetActionType.Action,
    )
    async def stage_7(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        return await _run_stage_widget(7, payload)

    @widget_action(
        tab=MENU_PIPELINE_CONTROL,
        title='Запустить всё',
        widget_action_type=WidgetActionType.Action,
        width=24,
    )
    async def run_all_stages(
        self, payload: WidgetActionInputSchema
    ) -> WidgetActionResponseSchema:
        try:
            async with AsyncSessionLocal() as session:
                created = await PipelineRunService(session).enqueue_run(
                    kind=PipelineRunKind.all,
                    source=PipelineRunSource.admin,
                )
        except PipelineRunConflict as exc:
            return WidgetActionResponseSchema(
                data=[
                    {
                        'status': 'conflict',
                        'run_id': str(exc.run_id),
                        'details_url': f'/pipeline/runs/{exc.run_id}',
                    }
                ]
            )
        return WidgetActionResponseSchema(
            data=[
                {
                    'status': 'queued',
                    'run_id': str(created.run_id),
                    'details_url': f'/pipeline/runs/{created.run_id}',
                }
            ]
        )
