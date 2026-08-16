"""Pydantic-схемы для запроса/ответа."""

from datetime import datetime

from pydantic import BaseModel, Field

from .constants import OUTPUT_DIR


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
    output_dir: str = OUTPUT_DIR
    timeout: int = 60000
    retry_count: int = 3
    qrator_bypass: bool = True


class DirectorInfo(BaseModel):
    """Информация о руководителе."""

    full_name: str | None = None
    inn: str | None = None
    position: str | None = None
    entry_date: str | None = None


class SearchResult(BaseModel):
    """Модель результата операции поиска."""

    success: bool  # Успешность операции
    # Meta
    name: str  # Название конкурента
    inn: str | None = None  # ИНН конкурента
    search_url: str | None = None  # URL страницы запроса
    timestamp: datetime = Field(
        default_factory=datetime.now
    )  # Дата и время операции
    # Items
    url: str | None = None  # URL страницы компании
    status: str | None = None  # Статус компании (Действующее/Ликвидировано)
    raw_text: str | None = None  # Полный текст из карточки компании Items.Text
    published_at: str | None = None  # Дата регистрации (из raw_text)
    region: str | None = None  # Город регистрации (из raw_text)
    extra: str | None = None  # Блок с руководителем (текст из raw_text)
    # metadata
    file_path: str | None = None  # Путь к файлу HTML страницы
    error: str | None = None  # Ошибка, если операция не удалась
    error_type: str | None = None  # Тип ошибки, если операция не удалась
    proxy_used: str | None = None  # Прокси, использованный для операции
    user_agent_used: str | None = None  # User-Agent для операции

    @property
    def director_name(self) -> str | None:
        """Извлечь имя директора из extra (обратная совместимость)."""
        if not self.extra:
            return None
        lines = self.extra.split('\n')
        return lines[0].strip() if lines else None

    @property
    def director_inn(self) -> str | None:
        """Извлечь ИНН директора из extra (обратная совместимость)."""
        if not self.extra:
            return None
        lines = self.extra.split('\n')
        for i, line in enumerate(lines):
            if line.strip() == 'ИНН' and i + 1 < len(lines):
                return lines[i + 1].strip()
        return None

    @property
    def director_position(self) -> str | None:
        """Извлечь должность директора из extra (обратная совместимость)."""
        if not self.extra:
            return None
        lines = self.extra.split('\n')
        for i, line in enumerate(lines):
            if line.strip() == 'Должность' and i + 1 < len(lines):
                return lines[i + 1].strip()
        return None

    @property
    def director_date(self) -> str | None:
        """Извлечь дату внесения в ЕГРЮЛ из extra (обратная совместимость)."""
        if not self.extra:
            return None
        lines = self.extra.split('\n')
        for i, line in enumerate(lines):
            if 'Дата внесения данных в ЕГРЮЛ' in line and i + 1 < len(lines):
                return lines[i + 1].strip()
        return None
