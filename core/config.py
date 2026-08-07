"""Конфигурация приложения из переменных окружения (.env).

Загружает и валидирует параметры подключения к Postgres через Pydantic.
Один источник правды для строки подключения: все части (user, password,
host, port, db) берутся из переменных POSTGRES_*, а database_url собирает
из них DSN.

Используется везде: database.py (engine), Alembic (env.py), воркеры.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из .env файла."""

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

    # ===== Redis =====
    redis_host: str = 'localhost'
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    @property
    def redis_url(self) -> str:
        """Собирает URL для подключения к Redis."""
        if self.redis_password:
            return f'redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}'
        return f'redis://{self.redis_host}:{self.redis_port}/{self.redis_db}'

    # ===== Celery =====
    # Отдельные номера БД Redis (не redis_db — та занята под дедуп-хэши
    # BP-1), чтобы очередь/результаты Celery не смешивались с бизнес-данными.
    celery_broker_db: int = 1
    celery_result_backend_db: int = 2

    @property
    def celery_broker_url(self) -> str:
        """Собирает URL брокера Celery (Redis)."""
        if self.redis_password:
            return f'redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.celery_broker_db}'
        return f'redis://{self.redis_host}:{self.redis_port}/{self.celery_broker_db}'

    @property
    def celery_result_backend_url(self) -> str:
        """Собирает URL result backend Celery (Redis)."""
        if self.redis_password:
            return f'redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.celery_result_backend_db}'
        return f'redis://{self.redis_host}:{self.redis_port}/{self.celery_result_backend_db}'

    # ===== Пути для хранения данных =====
    # Корневая папка для данных BP-1
    bp1_data_root: str = './src/bp1/data'

    @property
    def bp1_html_dir(self) -> str:
        """Папка для сохранения HTML файлов."""
        return str(Path(self.bp1_data_root) / 'html_pages')

    @property
    def bp1_raw_dir(self) -> str:
        """Папка для сохранения raw данных (JSON)."""
        return str(Path(self.bp1_data_root) / 'raw')

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

    # ===== FASTAPI SETTINGS =====
    app_title: str = 'Конкурентная разведка'
    description: str = 'API управлния проектом конкурентная разведка'

    # ===== CORS =====
    # Список разрешённых origin через запятую, например:
    # CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'

    @property
    def cors_origins_list(self) -> list[str]:
        """Разбирает CORS_ORIGINS в список origin для CORSMiddleware."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(',')
            if origin.strip()
        ]

    # ===== JWT =====
    jwt_secret_key: str
    jwt_expire_minutes: int = 60

    # ===== Сброс пароля =====
    password_reset_code_expire_minutes: int = 10

    # ===== AI-ассистент (BP-6, генерация action_item) =====
    deepseek_token: str
    deepseek_base_url: str = 'https://api.deepseek.com'
    deepseek_model: str = 'deepseek-chat'

    # ===== BP-7 (агент расширения источников) =====
    # Порог score, выше которого source_candidate переносится в source
    # (src/bp7/pipeline.py::SourceCandidatePromoter). Настраивается через
    # .env без правки кода.
    source_candidate_score_threshold: float = 0.5

    # ===== Админка (FastAdmin, монтируется в api/main.py на /admin) =====
    # FastAdmin читает свои настройки напрямую из os.environ на импорте, а не
    # из этого класса — раскладывает их туда api/admin/__init__.py, чтобы
    # единственным источником правды остался .env.
    admin_site_name: str = 'Кодик — админка'
    admin_language: str = 'ru'
    # Секрет подписи сессии админки. Пустой -> берётся jwt_secret_key
    # (см. api/admin/__init__.py), отдельный ключ заводить не обязательно.
    admin_secret_key: str | None = None
    # False — обязательное значение для локального http://localhost: иначе
    # кука сессии ставится только по HTTPS и вход молча не работает.
    # На проде (за TLS) выставить True.
    admin_session_cookie_secure: bool = False


settings = Settings()
