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

from typing import Any

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
from core.pipeline.models import PipelineControlMarker
from core.pipeline.registry import STAGES
from core.pipeline.runner import StageResult, run_all, run_stage


def _format_result(result: StageResult) -> dict[str, Any]:
    stub = ' [ЗАГЛУШКА]' if result.is_stub else ''
    return {
        'этап': f'{result.number}. {result.title}{stub}',
        'статус': 'OK' if result.ok else 'ОШИБКА',
        'подробности': result.result if result.ok else result.error,
    }


REPARSE_FIELD = 'пересобрать'
TRUE_PARSING_FIELD = 'реальный сбор'


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


async def _run_stage_widget(
    number: int, payload: WidgetActionInputSchema
) -> WidgetActionResponseSchema:
    reparse = _reparse_requested(payload)
    true_parsing = _true_parsing_requested(payload)
    try:
        result = await run_stage(
            number, reparse=reparse, true_parsing=true_parsing
        )
    except Exception as exc:  # неизвестный номер / preflight / сбой этапа
        descriptor = STAGES.get(number)
        result = StageResult(
            number=number,
            title=descriptor.title if descriptor else f'Этап {number}',
            is_stub=descriptor.is_stub if descriptor else False,
            ok=False,
            error=str(exc),
        )
    return WidgetActionResponseSchema(data=[_format_result(result)])


@register(PipelineControlMarker, sqlalchemy_sessionmaker=AsyncSessionLocal)
class PipelineControlAdmin(ReadOnlyModelAdmin):
    menu_section = MENU_PIPELINE_CONTROL
    verbose_name = 'Пайплайн'
    verbose_name_plural = 'Пайплайн'

    widget_actions = (
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
        results = await run_all()
        return WidgetActionResponseSchema(
            data=[_format_result(r) for r in results]
        )
