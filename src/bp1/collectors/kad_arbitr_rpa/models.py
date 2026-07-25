from datetime import datetime

from pydantic import BaseModel

from .constants import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RETRY_COUNT,
    DEFAULT_TIMEOUT_MS,
)


class ProxyConfig(BaseModel):
    """Конфигурация прокси-сервера."""

    server: str
    username: str | None = None
    password: str | None = None


class ParsingRequest(BaseModel):
    """Входные параметры для парсинга."""

    inn: str
    proxy: ProxyConfig | None = None
    user_agent: str | None = None
    headless: bool = True
    output_dir: str = DEFAULT_OUTPUT_DIR
    timeout: int = DEFAULT_TIMEOUT_MS
    retry_count: int = DEFAULT_RETRY_COUNT


class ParsingResult(BaseModel):
    """Результат парсинга."""

    success: bool
    inn: str
    file_path: str | None = None
    error: str | None = None
    timestamp: datetime
    proxy_used: str | None = None
    user_agent_used: str | None = None
