"""Юнит-тесты core.mail.send_email — без реальной сети.

send_email — чистый транспорт: шлёт ровно на переданный `to`, без скрытой
подмены получателя (та логика теперь в src/bp5/pipeline.py, см. test_crud.py
и test_pipeline.py). FastMail.send_message мокается через monkeypatch — эти
тесты не открывают ни одного сокета.
"""

from unittest.mock import AsyncMock

import pytest

import core.mail as mail_module
from core.mail import send_email


@pytest.fixture(autouse=True)
def mock_send_message(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(mail_module._fast_mail, 'send_message', mock)
    return mock


async def test_sends_to_passed_recipient(mock_send_message):
    await send_email('someone@real.example', 'Тема', 'Текст')

    mock_send_message.assert_awaited_once()
    sent_message = mock_send_message.await_args.args[0]
    # recipients хранится как NameEmail (email-validator), не голой строкой
    assert sent_message.recipients[0].email == 'someone@real.example'
    assert sent_message.subject == 'Тема'


async def test_send_failure_propagates(mock_send_message):
    mock_send_message.side_effect = RuntimeError('SMTP недоступен')

    with pytest.raises(RuntimeError, match='SMTP недоступен'):
        await send_email('someone@real.example', 'Тема', 'Текст')
