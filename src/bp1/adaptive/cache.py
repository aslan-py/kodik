"""
Единое кэширование для адаптивного пайплайна.

Хранит:
- Адаптеры (селекторы, схемы) — Redis TTL 7 дней
- Профили браузеров (cookies, состояние) — диск
- HTML-снапшоты — диск
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import AdapterState, SourceClassification

# TTL адаптера по умолчанию — 7 дней (в секундах).
ADAPTER_TTL_SECONDS = 86400 * 7

# TTL классификации источника по умолчанию — 7 дней (в секундах).
CLASSIFICATION_TTL_SECONDS = 86400 * 7


class UnifiedCache:
    """
    Единое кэширование для всех компонентов.

    Адаптеры хранятся в Redis (если клиент передан) с TTL 7 дней.
    Профили браузеров и HTML-снапшоты — на диске в cache_dir.
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
        return f'bp1:adapter:{source_name}'

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
        return f'bp1:classification:{source_name}'

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
    # Профили браузеров (диск)
    # ========================================================================

    def _profile_path(self, source_name: str) -> Path:
        safe_name = source_name.replace('/', '_').replace(':', '_')
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
        import hashlib

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
