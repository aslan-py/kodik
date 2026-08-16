"""HTTP-контракт проектной оболочки FastAdmin."""

import json
import re

from api.admin.navigation import EXPECTED_MODEL_ORDER


async def test_admin_index_contains_upstream_and_project_assets(client):
    response = await client.get('/admin/')

    assert response.status_code == 200
    assert 'lang="ru"' in response.text
    assert '/admin/static/index.min.js' in response.text
    assert '/admin/static/index.min.css' in response.text
    assert '/admin/ui/admin.js' in response.text
    assert '/admin/ui/admin.css' in response.text
    match = re.search(r'window\.KODIK_ADMIN_UI = (\{.*\});', response.text)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload['modelOrder'] == list(EXPECTED_MODEL_ORDER)


async def test_admin_local_ui_assets_are_served(client):
    css = await client.get('/admin/ui/admin.css')
    js = await client.get('/admin/ui/admin.js')

    assert css.status_code == 200
    assert css.headers['content-type'].startswith('text/css')
    assert "[data-kodik-zone='pipeline']" in css.text
    assert js.status_code == 200
    assert 'application/javascript' in js.headers['content-type']
    assert 'MutationObserver' in js.text
    assert '__KODIK_ADMIN_OBSERVER__' in js.text


async def test_upstream_static_and_api_paths_are_delegated(client):
    static = await client.get('/admin/static/index.min.css')
    configuration = await client.get('/admin/api/configuration')

    assert static.status_code == 200
    assert static.headers['content-type'].startswith('text/css')
    assert configuration.status_code == 200
    assert configuration.json()['models'] == []
