"""Единый источник структуры и порядка административной навигации."""

from dataclasses import asdict, dataclass
from typing import Any

from fastadmin.models.base import admin_models

from api.admin.base import (
    MENU_ADMIN_ALERTING,
    MENU_ADMIN_PARSING,
    MENU_ADMIN_REFERENCES,
    MENU_FINAL_TABLES,
    MENU_PIPELINE_CONTROL,
)


@dataclass(frozen=True)
class AdminSection:
    id: str
    title: str
    description: str
    zone: str
    models: tuple[str, ...]


ADMIN_SECTIONS = (
    AdminSection(
        id='pipeline',
        title=MENU_PIPELINE_CONTROL,
        description=(
            'Запуск отдельных этапов BP-1—BP-7 или всего конвейера. '
            'Результат каждого запуска отображается на этой странице.'
        ),
        zone='pipeline',
        models=('PipelineControlMarker',),
    ),
    AdminSection(
        id='parsing',
        title=MENU_ADMIN_PARSING,
        description=(
            'Конкуренты, источники, триггеры и задачи, по которым BP-1 '
            'собирает материалы.'
        ),
        zone='settings',
        models=('Competitor', 'Source', 'Trigger', 'SearchTask'),
    ),
    AdminSection(
        id='references',
        title=MENU_ADMIN_REFERENCES,
        description=(
            'Справочники очистки и разметки данных, отделы и пользователи '
            'системы.'
        ),
        zone='settings',
        models=(
            'Region',
            'BlackDomain',
            'StopWord',
            'TopicLimit',
            'Category',
            'Department',
            'User',
        ),
    ),
    AdminSection(
        id='alerting',
        title=MENU_ADMIN_ALERTING,
        description=(
            'Типы событий, каналы доставки и правила выбора получателей '
            'уведомлений.'
        ),
        zone='settings',
        models=('EventType', 'Channel', 'RoutingRule'),
    ),
    AdminSection(
        id='final',
        title=MENU_FINAL_TABLES,
        description=(
            'Результаты этапов BP-1—BP-7 в порядке прохождения данных. '
            'Большинство таблиц доступны только для просмотра.'
        ),
        zone='final',
        models=(
            'RawItem',
            'NormalizedItem',
            'CategorizedEvent',
            'ShowcaseEvent',
            'Alert',
            'ActionItem',
            'SourceCandidate',
        ),
    ),
)

EXPECTED_MODEL_ORDER = tuple(
    model_name for section in ADMIN_SECTIONS for model_name in section.models
)
HIDDEN_MENU_MODELS = ('PipelineControlMarker',)


def configure_admin_navigation() -> None:
    """Проверить полный registry, назначить секции и закрепить порядок."""
    registered = {
        model.__name__: (model, admin) for model, admin in admin_models.items()
    }
    expected = set(EXPECTED_MODEL_ORDER)
    actual = set(registered)
    if actual != expected or len(registered) != len(EXPECTED_MODEL_ORDER):
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise RuntimeError(
            'FastAdmin registry не соответствует навигации: '
            f'missing={missing}, unexpected={unexpected}'
        )

    ordered: dict[Any, Any] = {}
    for section in ADMIN_SECTIONS:
        for model_name in section.models:
            model, admin = registered[model_name]
            admin.menu_section = section.title
            ordered[model] = admin
    admin_models.clear()
    admin_models.update(ordered)


def navigation_payload() -> dict[str, Any]:
    return {
        'sections': [asdict(section) for section in ADMIN_SECTIONS],
        'modelOrder': list(EXPECTED_MODEL_ORDER),
        'hiddenModels': list(HIDDEN_MENU_MODELS),
    }
