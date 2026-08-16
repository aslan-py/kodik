"""Статический browser-контракт fail-soft UI-adapter и responsive CSS."""

from pathlib import Path

_UI_DIR = Path(__file__).parents[2] / 'api' / 'admin' / 'ui'


def test_ui_adapter_uses_stable_menu_ids_and_single_observer():
    script = (_UI_DIR / 'admin.js').read_text(encoding='utf-8')

    assert "document.querySelectorAll('[data-menu-id]')" in script
    assert '.endsWith(`-${key}`)' in script
    assert "menuItemByKey('dashboard')" in script
    assert 'menuItemByKey(`section-${section.title}`)' in script
    assert script.count('new MutationObserver') == 1
    assert '__KODIK_ADMIN_OBSERVER__' in script
    assert 'window.requestAnimationFrame' in script
    assert 'observer?.disconnect()' in script
    assert "dataset.kodikHidden = 'true'" in script
    assert "dashboard.dataset.kodikZone = 'pipeline'" in script
    assert "textContent = 'Пайплайн'" in script


def test_ui_adapter_has_idempotent_banner_and_direct_url_detection():
    script = (_UI_DIR / 'admin.js').read_text(encoding='utf-8')

    assert "document.querySelector('.kodik-section-banner')" in script
    assert 'existing.dataset.kodikSection !== section.id' in script
    assert 'window.location.pathname' in script
    assert 'window.location.hash' in script
    assert "banner.setAttribute('role', 'note')" in script
    assert 'content.prepend(banner)' in script
    assert "document.querySelector('.ant-layout > .ant-card')" in script
    assert 'document.querySelector(\'[class*="content"]\')' not in script


def test_css_covers_three_zones_themes_compact_and_minimum_width():
    styles = (_UI_DIR / 'admin.css').read_text(encoding='utf-8')

    for zone in ('pipeline', 'settings', 'final'):
        assert f"[data-kodik-zone='{zone}']" in styles
    assert "[data-theme='dark']" in styles
    assert '.ant-layout-sider-dark' in styles
    assert '.ant-layout-sider-collapsed [data-kodik-zone]' in styles
    assert '@media (max-width: 768px)' in styles
    assert 'overflow-x: hidden' in styles
    assert '.ant-menu-item-selected' in styles
