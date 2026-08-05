"""Общие фикстуры API-тестов.

`session` берётся из tests/conftest.py (без commit, откат после теста).
Сервисы api/service/* сами вызывают session.commit() (не только flush,
как CRUD в src/bp*/crud.py) — если дать этому commit'у реально сработать
в тесте, данные утекут в БД мимо отката фикстуры. Подменяем commit на
no-op: CRUD-методы всё равно делают flush() перед ним, так что изменения
видны в транзакции, а откат в конце теста (tests/conftest.py::session)
работает как обычно, потому что до реальной БД commit не доходит — тот же
принцип изоляции, что и в tests/bp5/test_crud.py, где run_bp5() (с
реальным commit) в тестах никогда не вызывается напрямую.
"""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def no_commit(session, monkeypatch):
    monkeypatch.setattr(session, 'commit', AsyncMock())
