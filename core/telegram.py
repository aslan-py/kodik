"""Отправка сообщений в Telegram через aiogram. Единая точка входа для BP-5.

Чистый транспорт — send_telegram шлёт сообщение ровно в переданный `chat_id`,
без скрытой подмены получателя (та же схема, что и core/mail.py). Кому
реально слать (тестовый chat_id или настоящий пользователя) решает
вызывающий код (src/bp5/pipeline.py) на основе settings.true_alerting.
"""

from aiogram import Bot

from core.config import settings

_bot = Bot(token=settings.telegram_bot_token)


async def send_telegram(chat_id: int, text: str) -> None:
    """Отправить сообщение. Бросает исключение при сбое Telegram API —
    вызывающий код (src/bp5/pipeline.py) ловит и решает queued -> sent/failed.
    """
    await _bot.send_message(chat_id=chat_id, text=text)


# if __name__ == '__main__':
#     import asyncio

#     async def test_telegram_sending() -> None:
#         print('Начинаем тест отправки...')
#         try:
#             await send_telegram(
#                 chat_id=settings.test_tg,
#                 text='Тестовый алерт из BP-5 (Telegram).',
#             )
#             print('Успех: сообщение отправлено.')
#         except Exception as e:
#             print(f'Ошибка при отправке: {e}')

#     asyncio.run(test_telegram_sending())
