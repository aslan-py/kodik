"""
Единое кэширование для адаптивного пайплайна.

Хранит:
- Адаптеры (селекторы, схемы) — Redis TTL 7 дней
- Профили браузеров (cookies, состояние) — диск
- HTML-снапшоты — диск
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from core.config import settings

from ..schemas import AdapterState, ProbedUrl, SourceClassification

# TTL адаптера по умолчанию — 7 дней (в секундах).
ADAPTER_TTL_SECONDS = settings.bp1_adapter_ttl_seconds

# TTL классификации источника по умолчанию — 7 дней (в секундах).
CLASSIFICATION_TTL_SECONDS = settings.bp1_classification_ttl_seconds

# TTL кэша полного текста статьи по умолчанию — 7 дней (в секундах).
ARTICLE_TEXT_TTL_SECONDS = settings.bp1_article_text_ttl_seconds

# TTL кэша пробинга поискового URL по умолчанию — 7 дней (в секундах).
PROBED_URL_TTL_SECONDS = settings.bp1_probed_url_ttl_seconds


def _canonical_source_name(source_name: str) -> str:
    """Приводит имя источника к каноническому hostname в нижнем регистре.

    Источники в базе могут храниться как полный URL (``https://lenta.ru/``),
    голый домен (``lenta.ru``) или с ``www``. Чтобы адаптер, классификация и
    профиль находились независимо от формы ввода, ключ приводится к единому
    hostname. Если значение не похоже на корректный источник/URL — возвращается
    исходная строка без изменений (fallback).

    Логика продублирована из ``integration.sources.extract_host`` намеренно,
    чтобы избежать циклического импорта (``sources`` импортирует ``cache``).
    """
    value = (source_name or '').strip()
    if not value or any(ch.isspace() for ch in value):
        return source_name
    try:
        host = urlsplit(
            value if '://' in value else f'https://{value}'
        ).hostname
        if not host:
            return source_name
    except Exception:
        return source_name
    host = host.lower()
    if host.startswith('www.'):
        host = host[4:]
    return host


class UnifiedCache:
    """
    Единое кэширование для всех компонентов.

    Адаптеры хранятся в Redis (если клиент передан) с TTL 7 дней.
    Профили браузеров и HTML-снапшоты — на диске в cache_dir.

    Все ключи (адаптер, классификация) и имена файлов профилей приводятся
    к каноническому hostname источника, поэтому ``lenta.ru``,
    ``https://lenta.ru/`` и ``https://www.lenta.ru/news`` дают один и тот же
    ключ. За счёт этого данные находятся независимо от формы ``--source``.
    """

    def __init__(
        self,
        redis_client: Any = None,
        cache_dir: str = './src/bp1/data/cache',
    ):
        self.redis = redis_client
        self.cache_dir = Path(cache_dir)
        self._profiles_dir = self.cache_dir / 'profiles'
        self._snapshots_dir = self.cache_dir / 'snapshots'
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # Адаптеры (Redis)
    # ========================================================================

    def _adapter_key(self, source_name: str) -> str:
        return f'bp1:adapter:{_canonical_source_name(source_name)}'

    async def get_adapter(self, source_name: str) -> AdapterState | None:
        """Получить адаптер из Redis."""
        if self.redis is None:
            return None
        raw = await self.redis.get(self._adapter_key(source_name))
        if not raw:
            return None
        try:
            return AdapterState.model_validate_json(raw)
        except Exception:
            return None

    async def set_adapter(
        self,
        source_name: str,
        adapter: AdapterState,
        ttl: int = ADAPTER_TTL_SECONDS,
    ) -> None:
        """Сохранить адаптер в Redis (TTL 7 дней)."""
        if self.redis is None:
            return
        await self.redis.set(
            self._adapter_key(source_name),
            adapter.model_dump_json(),
            ex=ttl,
        )

    async def clear_adapter(self, source_name: str) -> None:
        """Удалить адаптер из Redis."""
        if self.redis is None:
            return
        await self.redis.delete(self._adapter_key(source_name))

    # ========================================================================
    # Классификация источников (Redis)
    # ========================================================================

    def _classification_key(self, source_name: str) -> str:
        return f'bp1:classification:{_canonical_source_name(source_name)}'

    async def get_classification(
        self, source_name: str
    ) -> SourceClassification | None:
        """Получить классификацию источника из Redis."""
        if self.redis is None:
            return None
        raw = await self.redis.get(self._classification_key(source_name))
        if not raw:
            return None
        try:
            return SourceClassification.model_validate_json(raw)
        except Exception:
            return None

    async def set_classification(
        self,
        source_name: str,
        classification: SourceClassification,
        ttl: int = CLASSIFICATION_TTL_SECONDS,
    ) -> None:
        """Сохранить классификацию источника в Redis (TTL 7 дней)."""
        if self.redis is None:
            return
        await self.redis.set(
            self._classification_key(source_name),
            classification.model_dump_json(),
            ex=ttl,
        )

    async def clear_classification(self, source_name: str) -> None:
        """Удалить классификацию источника из Redis."""
        if self.redis is None:
            return
        await self.redis.delete(self._classification_key(source_name))

    # ========================================================================
    # Пробинг поискового URL (Redis)
    # ========================================================================

    def _probed_url_key(self, source_name: str) -> str:
        return f'bp1:probed_url:{_canonical_source_name(source_name)}'

    async def get_probed_url(self, source_name: str) -> ProbedUrl | None:
        """Получить закэшированный probed URL источника из Redis.

        Возвращает ``None``, если ключа нет или значение повреждено.
        """
        if self.redis is None:
            return None
        raw = await self.redis.get(self._probed_url_key(source_name))
        if not raw:
            return None
        try:
            return ProbedUrl.model_validate_json(raw)
        except Exception:
            return None

    async def set_probed_url(
        self,
        source_name: str,
        probed: ProbedUrl,
        ttl: int = PROBED_URL_TTL_SECONDS,
    ) -> None:
        """Сохранить probed URL источника в Redis (TTL 7 дней)."""
        if self.redis is None:
            return
        await self.redis.set(
            self._probed_url_key(source_name),
            probed.model_dump_json(),
            ex=ttl,
        )

    async def clear_probed_url(self, source_name: str) -> None:
        """Удалить probed URL источника из Redis."""
        if self.redis is None:
            return
        await self.redis.delete(self._probed_url_key(source_name))

    # ========================================================================
    # Профили браузеров (диск)
    # ========================================================================

    def _profile_path(self, source_name: str) -> Path:
        safe_name = _canonical_source_name(source_name)
        return self._profiles_dir / f'{safe_name}.json'

    async def get_profile(self, source_name: str) -> dict | None:
        """Получить профиль браузера."""
        path = self._profile_path(source_name)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return None

    async def set_profile(self, source_name: str, profile: dict) -> None:
        """Сохранить профиль браузера."""
        path = self._profile_path(source_name)
        path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    # ========================================================================
    # HTML-снапшоты (диск)
    # ========================================================================

    def _snapshot_path(self, url: str) -> Path:
        digest = hashlib.md5(url.encode('utf-8')).hexdigest()
        return self._snapshots_dir / f'{digest}.html'

    async def get_snapshot(self, url: str) -> str | None:
        """Получить HTML-снапшот."""
        path = self._snapshot_path(url)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding='utf-8')
        except Exception:
            return None

    async def set_snapshot(self, url: str, html: str) -> None:
        """Сохранить HTML-снапшот."""
        path = self._snapshot_path(url)
        path.write_text(html, encoding='utf-8')

    # ========================================================================
    # Полный текст статьи по URL (диск)
    #
    # Кэширует извлечённый полный текст новости (ex_text) по абсолютному URL
    # статьи, чтобы повторные запуски глубокого фетча не тратили LLM-токены и
    # не скачивали страницу заново. Хранится на диске рядом со снапшотами.
    # ========================================================================

    def _article_text_path(self, url: str) -> Path:
        digest = hashlib.md5(url.encode('utf-8')).hexdigest()
        return self._snapshots_dir / f'article_{digest}.json'

    async def get_article_text(self, url: str) -> dict | None:
        """Получить кэшированный полный текст статьи (``{"text", "method"}``).

        Возвращает ``None``, если кэш пуст или файл повреждён.
        """
        path = self._article_text_path(url)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return None

    async def set_article_text(
        self,
        url: str,
        text: str,
        method: str,
        ttl: int = ARTICLE_TEXT_TTL_SECONDS,
    ) -> None:
        """Сохранить полный текст статьи в кэш по ``url``."""
        path = self._article_text_path(url)
        path.write_text(
            json.dumps(
                {'text': text, 'method': method},
                ensure_ascii=False,
            ),
            encoding='utf-8',
        )

    # ========================================================================
    # Circuit breaker источников (Redis)
    #
    # Двухуровневая защита от недоступных источников:
    # 1. ``source_blocked:<src>`` — временная блокировка на TTL (circuit
    #    breaker). Пока ключ существует, источник не пробуют парсить.
    # 2. ``source_fail_count:<src>`` — счётчик подряд идущих полных отказов.
    #    При достижении порога источник отключается в БД (is_active=False).
    # ========================================================================

    def _blocked_key(self, source_name: str) -> str:
        return f'bp1:source_blocked:{_canonical_source_name(source_name)}'

    def _fail_count_key(self, source_name: str) -> str:
        return f'bp1:source_fail_count:{_canonical_source_name(source_name)}'

    async def is_source_blocked(self, source_name: str) -> bool:
        """Проверить, временно ли заблокирован источник в Redis."""
        if self.redis is None:
            return False
        return bool(await self.redis.exists(self._blocked_key(source_name)))

    async def block_source(
        self,
        source_name: str,
        ttl: int = 86400,
    ) -> None:
        """Временно заблокировать источник в Redis на ``ttl`` секунд."""
        if self.redis is None:
            return
        await self.redis.set(self._blocked_key(source_name), '1', ex=ttl)

    async def unblock_source(self, source_name: str) -> None:
        """Снять временную блокировку источника (при успешном парсинге)."""
        if self.redis is None:
            return
        await self.redis.delete(self._blocked_key(source_name))

    async def increment_fail_count(self, source_name: str) -> int:
        """Инкрементировать счётчик отказов. Возвращает новое значение."""
        if self.redis is None:
            return 0
        return int(await self.redis.incr(self._fail_count_key(source_name)))

    async def get_fail_count(self, source_name: str) -> int:
        """Текущее значение счётчика отказов (без инкремента)."""
        if self.redis is None:
            return 0
        raw = await self.redis.get(self._fail_count_key(source_name))
        try:
            return int(raw) if raw else 0
        except (TypeError, ValueError):
            return 0

    async def reset_fail_count(self, source_name: str) -> None:
        """Сбросить счётчик отказов (при успешном парсинге)."""
        if self.redis is None:
            return
        await self.redis.delete(self._fail_count_key(source_name))
