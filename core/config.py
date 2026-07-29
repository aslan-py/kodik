"""Конфигурация приложения из переменных окружения (.env).

Загружает и валидирует параметры подключения к Postgres через Pydantic.
Один источник правды для строки подключения: все части (user, password,
host, port, db) берутся из переменных POSTGRES_*, а database_url собирает
из них DSN.

Используется везде: database.py (engine), Alembic (env.py), воркеры.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    # ===== Postgres =====
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = 'localhost'
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """Динамически собирает DSN-строку подключения к БД."""
        return (
            f'postgresql+asyncpg://{self.postgres_user}:'
            f'{self.postgres_password}@{self.postgres_host}:'
            f'{self.postgres_port}/{self.postgres_db}'
        )

    # ===== Mail =====
    mail_username: str
    mail_password: str
    mail_from: str
    mail_from_name: str = 'Kodik Alerts'
    mail_port: int = 465
    mail_server: str
    mail_starttls: bool = False
    mail_ssl_tls: bool = True
    mail_use_credentials: bool = True
    mail_validate_certs: bool = True

    # ===== Telegram =====
    telegram_bot_token: str
    test_tg: int

    # ===== Alerting =====
    true_alerting: bool = False
    test_email: str


settings = Settings()
