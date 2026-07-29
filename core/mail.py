"""Отправка email через SMTP (fastapi-mail). Единая точка входа для BP-5.

Чистый транспорт — send_email шлёт письмо ровно на переданный `to`, без
скрытой подмены получателя. Кому реально слать (тестовый песочничный адрес
или настоящий адрес пользователя) решает вызывающий код (src/bp5/pipeline.py)
на основе settings.true_alerting — здесь эта логика больше не живёт.
"""

import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from core.config import settings

logger = logging.getLogger(__name__)

_connection_config = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_STARTTLS=settings.mail_starttls,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    USE_CREDENTIALS=settings.mail_use_credentials,
    VALIDATE_CERTS=settings.mail_validate_certs,
)
_fast_mail = FastMail(_connection_config)


async def send_email(to: str, subject: str, body: str) -> None:
    """Отправить письмо через SMTP. Бросает исключение при сбое —
    вызывающий код (src/bp5/pipeline.py) ловит и решает queued -> sent/failed.
    """
    message = MessageSchema(
        recipients=[to],
        subject=subject,
        body=body,
        subtype=MessageType.plain,
    )
    await _fast_mail.send_message(message)


# if __name__ == '__main__':
#     import asyncio

#     async def test_mail_sending() -> None:
#         print('Начинаем тест отправки...')
#         try:
#             await send_email(
#                 to=settings.test_email,
#                 subject='Тестовый алерт из BP-5',
#                 body='Привет! Это тестовая проверка отправки писем.',
#             )
#             print('Успех: письмо отправлено.Проверяйте ящик (и папку Спам)!')
#         except Exception as e:
#             print(f'Ошибка при отправке: {e}')

#     asyncio.run(test_mail_sending())
