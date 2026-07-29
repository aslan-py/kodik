"""Pydantic-схемы для запроса/ответа."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    """Конфигурация прокси-сервера."""

    server: str
    username: str | None = None
    password: str | None = None


class SearchRequest(BaseModel):
    """Модель запроса для операции поиска."""

    name: str
    inn: str | None = None
    proxy: ProxyConfig | None = None
    user_agent: str | None = None
    headless: bool | None = None  # None = значение парсера по умолчанию
    output_dir: str = './parsed_pages'
    timeout: int = 60000
    retry_count: int = 3
    qrator_bypass: bool = True


class SearchResult(BaseModel):
    """Модель результата операции поиска."""

    success: bool
    name: str
    inn: str | None = None
    status: str | None = None  # Статус компании (Действующее/Ликвидировано)
    raw_text: str | None = None  # Полный текст из карточки компании
    file_path: str | None = None
    error: str | None = None
    error_type: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    proxy_used: str | None = None
    user_agent_used: str | None = None

    @property
    def html_content(self) -> str | None:
        """Обратная совместимость: html_content возвращает raw_text."""
        return self.raw_text
