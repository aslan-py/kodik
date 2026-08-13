"""Backend-контракт структуры меню FastAdmin."""

from fastadmin.models.base import admin_models

from api.admin.base import KodikModelAdmin, ReadOnlyModelAdmin
from api.admin.navigation import (
    ADMIN_SECTIONS,
    EXPECTED_MODEL_ORDER,
    HIDDEN_MENU_MODELS,
    navigation_payload,
)
from api.admin.pipeline_control import PipelineControlAdmin
from api.admin.users import UserAdmin
from api.admin.workflow import ActionItemAdmin, ShowcaseEventAdmin


def test_sections_have_exact_titles_zones_and_models():
    assert [
        (section.id, section.title, section.zone) for section in ADMIN_SECTIONS
    ] == [
        ('pipeline', 'Пайплайн', 'pipeline'),
        ('parsing', 'Настройки парсинга', 'settings'),
        ('references', 'Настройки справочников', 'settings'),
        ('alerting', 'Настройки алертинга', 'settings'),
        ('final', 'Финальные таблицы', 'final'),
    ]
    assert [section.models for section in ADMIN_SECTIONS] == [
        ('PipelineControlMarker', 'PipelineRun', 'PipelineStageRun'),
        ('Competitor', 'Source', 'Trigger', 'SearchTask'),
        (
            'Region',
            'BlackDomain',
            'StopWord',
            'TopicLimit',
            'Category',
            'Department',
            'User',
        ),
        ('EventType', 'Channel', 'RoutingRule'),
        (
            'RawItem',
            'NormalizedItem',
            'CategorizedEvent',
            'ShowcaseEvent',
            'Alert',
            'ActionItem',
            'SourceCandidate',
        ),
    ]
    assert all(section.description for section in ADMIN_SECTIONS)


def test_fastadmin_registry_has_exact_order_and_sections():
    assert (
        tuple(model.__name__ for model in admin_models) == EXPECTED_MODEL_ORDER
    )
    expected_sections = {
        model: section.title
        for section in ADMIN_SECTIONS
        for model in section.models
    }
    assert {
        model.__name__: admin.menu_section
        for model, admin in admin_models.items()
    } == expected_sections


def test_payload_is_single_source_for_ui_adapter():
    payload = navigation_payload()
    assert payload['modelOrder'] == list(EXPECTED_MODEL_ORDER)
    assert payload['hiddenModels'] == list(HIDDEN_MENU_MODELS)
    assert [section['title'] for section in payload['sections']] == [
        section.title for section in ADMIN_SECTIONS
    ]


def test_moved_admin_classes_keep_permissions_and_base_classes():
    assert issubclass(UserAdmin, KodikModelAdmin)
    assert UserAdmin.menu_section == 'Настройки справочников'
    assert 'has_change_permission' in UserAdmin.__dict__
    assert issubclass(ShowcaseEventAdmin, ReadOnlyModelAdmin)
    assert ShowcaseEventAdmin.menu_section == 'Финальные таблицы'
    assert issubclass(ActionItemAdmin, KodikModelAdmin)
    assert not issubclass(ActionItemAdmin, ReadOnlyModelAdmin)
    assert ActionItemAdmin.menu_section == 'Финальные таблицы'


def test_pipeline_marker_stays_registered_with_all_widget_actions():
    marker_admin = next(
        admin
        for model, admin in admin_models.items()
        if model.__name__ == 'PipelineControlMarker'
    )
    assert isinstance(marker_admin, PipelineControlAdmin)
    assert marker_admin.widget_actions == (
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
    assert all(
        getattr(getattr(marker_admin, action), 'is_widget_action', False)
        for action in marker_admin.widget_actions
    )


async def test_read_only_crud_and_user_permissions_are_preserved(monkeypatch):
    showcase = next(
        admin
        for model, admin in admin_models.items()
        if model.__name__ == 'ShowcaseEvent'
    )
    action_item = next(
        admin
        for model, admin in admin_models.items()
        if model.__name__ == 'ActionItem'
    )
    user = next(
        admin
        for model, admin in admin_models.items()
        if model.__name__ == 'User'
    )

    assert await showcase.has_add_permission() is False
    assert await showcase.has_change_permission() is False
    assert await action_item.has_add_permission() is True
    assert await action_item.has_change_permission() is True

    async def admin_role(_user_id):
        from core.enums import UserRole

        return UserRole.admin

    async def analyst_role(_user_id):
        from core.enums import UserRole

        return UserRole.analyst

    monkeypatch.setattr('api.admin.users._get_role', admin_role)
    assert await user.has_change_permission(1) is True
    monkeypatch.setattr('api.admin.users._get_role', analyst_role)
    assert await user.has_change_permission(1) is False
