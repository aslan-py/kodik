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


settings = Settings()
