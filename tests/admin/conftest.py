"""Локальный ASGI-клиент для тестов административной оболочки."""

from collections.abc import AsyncIterator

import httpx
import pytest

from api.main import app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url='http://testserver'
    ) as test_client:
        yield test_client
