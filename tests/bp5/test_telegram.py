"""Юнит-тесты core.telegram.send_telegram — без реальной сети.

send_telegram — чистый транспорт: шлёт ровно в переданный `chat_id`, без
скрытой подмены получателя (та логика — в src/bp5/pipeline.py, см.
test_crud.py). aiogram Bot.send_message мокается через monkeypatch — эти
тесты не открывают ни одного сокета.
"""

from unittest.mock import AsyncMock

import pytest

import core.telegram as telegram_module
from core.telegram import send_telegram


@pytest.fixture(autouse=True)
def mock_send_message(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(telegram_module._bot, 'send_message', mock)
    return mock


async def test_sends_to_passed_chat_id(mock_send_message):
    await send_telegram(302355541, 'Текст алерта')

    mock_send_message.assert_awaited_once_with(
        chat_id=302355541, text='Текст алерта'
    )


async def test_send_failure_propagates(mock_send_message):
    mock_send_message.side_effect = RuntimeError('Telegram API недоступен')

    with pytest.raises(RuntimeError, match='Telegram API недоступен'):
        await send_telegram(302355541, 'Текст алерта')
