"""Тесты генератора кода сброса пароля (api/security.py)."""

from api.security import generate_reset_code


def test_generate_reset_code_is_always_six_digits():
    for _ in range(200):
        code = generate_reset_code()
        assert len(code) == 6
        assert code.isdigit()


def test_generate_reset_code_keeps_leading_zeros(monkeypatch):
    monkeypatch.setattr('api.security.secrets.randbelow', lambda _: 42)
    assert generate_reset_code() == '000042'
