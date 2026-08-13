"""Проектная ASGI-оболочка над штатным приложением FastAdmin."""

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from api.admin.navigation import navigation_payload

_UI_DIR = Path(__file__).with_name('ui')
_INDEX_TEMPLATE = _UI_DIR / 'index.html'


def _admin_prefix() -> str:
    return os.getenv('ADMIN_PREFIX', 'admin').strip('/')


def _index_html() -> str:
    payload = json.dumps(
        navigation_payload(), ensure_ascii=False, separators=(',', ':')
    ).replace('</', '<\\/')
    return (
        _INDEX_TEMPLATE.read_text(encoding='utf-8')
        .replace('{{ADMIN_PREFIX}}', _admin_prefix())
        .replace('{{KODIK_ADMIN_UI}}', payload)
    )


def create_admin_app(upstream_app) -> FastAPI:
    app = FastAPI(title='Kodik Admin', openapi_url=None)

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(_index_html())

    @app.get('/ui/admin.css', include_in_schema=False)
    async def admin_css() -> FileResponse:
        return FileResponse(_UI_DIR / 'admin.css', media_type='text/css')

    @app.get('/ui/admin.js', include_in_schema=False)
    async def admin_js() -> FileResponse:
        return FileResponse(
            _UI_DIR / 'admin.js', media_type='application/javascript'
        )

    app.mount('/', upstream_app)
    return app
