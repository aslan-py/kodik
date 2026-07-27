"""Pydantic-схемы BP-2: валидация и нормализация одного события.

RawEventIn берёт один сырой объект из raw_data.items[] (уже прошедший
clean_text в split_items) и приводит его к типизированному виду, делая ТОЛЬКО
то, что не требует БД:

    - title: пусто/нет → заглушка TITLE_PLACEHOLDER (в БД title NOT NULL,
      «безымянное» событие иначе не сохранить). normalize_item по этой
      заглушке ставит reject_reason=parse_error;
    - published_at парсится из сырой строки («26 июня 2026», «23.06.2026»,
      ISO) в date; что не распарсили — None;
    - media_domain вычисляется из url (netloc без www) — вход для black_domain;
    - competitor / region остаются сырыми строками-ИМЕНАМИ: их lookup в id
      делает normalize_item через справочники Bp2Crud (нужна БД).

Ключи сырого JSON совпадают с именами колонок normalized_item (published_at,
media_name, ...) — поэтому alias'ов нет. Исключение по смыслу: competitor/
region (имя, не id) и media_domain (производное от url).

Дедуп-ключ и проставление competitor_id/region_id/source_id — тоже забота
normalize_item, не схемы.
"""

from datetime import date
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# Заглушка для события без заголовка: title в БД NOT NULL, поэтому пустой
# заголовок подменяем, а normalize_item по этому значению ставит parse_error.
TITLE_PLACEHOLDER = 'без заголовка'

# Русские месяцы в родительном падеже («26 июня») → номер.
_RU_MONTHS = {
    'января': 1,
    'февраля': 2,
    'марта': 3,
    'апреля': 4,
    'мая': 5,
    'июня': 6,
    'июля': 7,
    'августа': 8,
    'сентября': 9,
    'октября': 10,
    'ноября': 11,
    'декабря': 12,
}


def parse_ru_date(value: object) -> date | None:
    """Разобрать сырую дату в date. Что не распознали — None (поле nullable).

    Поддерживаем форматы, которые реально встречаются в источниках:
        - date как есть (уже разобран выше по конвейеру);
        - ISO: «2026-06-25»;
        - числовой: «23.06.2026»;
        - русский текст: «26 июня 2026».
    """
    if value is None or isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None

    try:
        return date.fromisoformat(s)  # «2026-06-25»
    except ValueError:
        pass

    if '.' in s:  # «23.06.2026»
        try:
            day, month, year = (int(p) for p in s.split('.'))
            return date(year, month, day)
        except (ValueError, TypeError):
            return None

    parts = s.split()  # «26 июня 2026»
    if len(parts) == 3 and parts[1].lower() in _RU_MONTHS:
        try:
            return date(
                int(parts[2]), _RU_MONTHS[parts[1].lower()], int(parts[0])
            )
        except ValueError:
            return None

    return None


def domain_from_url(url: str | None) -> str | None:
    """Домен публикатора из url: netloc в нижнем регистре без ведущего www."""
    if not url:
        return None
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]
    return netloc or None


class RawEventIn(BaseModel):
    """Одно валидированное событие из raw_data.items[] (факты, без id).

    Принимает плоский dict из split_items. Имена полей = ключам сырого JSON
    (и колонкам normalized_item). Незнакомые ключи («source», «trigger»)
    игнорируются.
    """

    model_config = ConfigDict(extra='ignore')

    search_task_id: int | None = None
    competitor: str | None = None
    region: str | None = None
    title: str = TITLE_PLACEHOLDER
    url: str | None = None
    text: str | None = None
    media_name: str | None = None
    media_domain: str | None = None
    published_at: date | None = None
    extra: dict = Field(default_factory=dict)

    @field_validator('title', mode='before')
    @classmethod
    def _title_or_placeholder(cls, value: object) -> object:
        # None/пусто (в т.ч. после clean_text) → заглушка: title NOT NULL.
        if isinstance(value, str):
            value = value.strip()
        return value or TITLE_PLACEHOLDER

    @field_validator('published_at', mode='before')
    @classmethod
    def _parse_date(cls, value: object) -> date | None:
        return parse_ru_date(value)

    @model_validator(mode='after')
    def _set_media_domain(self) -> 'RawEventIn':
        # media_domain во входе нет — выводим из уже разобранного url.
        self.media_domain = domain_from_url(self.url)
        return self
