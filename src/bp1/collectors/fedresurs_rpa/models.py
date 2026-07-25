"""Pydantic models for request/response."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    server: str
    username: str | None = None
    password: str | None = None


class SearchRequest(BaseModel):
    """Request model for search operation."""

    name: str
    inn: str | None = None
    proxy: ProxyConfig | None = None
    user_agent: str | None = None
    headless: bool | None = None  # None = use parser default
    output_dir: str = "./parsed_pages"
    timeout: int = 60000
    retry_count: int = 3
    qrator_bypass: bool = True


class SearchResult(BaseModel):
    """Result model for search operation."""

    success: bool
    name: str
    inn: str | None = None
    file_path: str | None = None
    html_content: str | None = None
    error: str | None = None
    error_type: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    proxy_used: str | None = None
    user_agent_used: str | None = None
