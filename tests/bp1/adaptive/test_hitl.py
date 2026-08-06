"""Тесты для HITLManager (персистентность запросов и профилей)."""

import pytest

from src.bp1.adaptive.schemas import HITLRequest
from src.bp1.adaptive.strategies.hitl import HITLManager, ProfileManager

from .constants import (
    EXAMPLE_URL,
    HITL_CACHE_DIR,
    HITL_JSON_GLOB,
    HITL_NONEXISTENT_ID,
    HITL_PROFILES_DIR,
    HITL_REQUEST_ID_1,
    HITL_REQUEST_ID_2,
    HITL_REQUEST_ID_3,
    HITL_REQUESTS_DIR,
    HITL_STATUS_NOT_FOUND,
    HITL_STATUS_PENDING,
    HITL_STATUS_RESOLVED,
)


class TestProfileManagerUnifiedCache:
    """Унификация ProfileManager с UnifiedCache."""

    def test_profile_manager_accepts_cache(self, tmp_path):
        from src.bp1.adaptive.core.cache import UnifiedCache

        cache = UnifiedCache(cache_dir=str(tmp_path / HITL_CACHE_DIR))
        pm = ProfileManager(
            profiles_dir=str(tmp_path / HITL_PROFILES_DIR), cache=cache
        )
        assert pm._cache is cache

    def test_profile_manager_without_cache(self, tmp_path):
        pm = ProfileManager(profiles_dir=str(tmp_path))
        assert pm._cache is None


class TestHITLRequestPersistence:
    """Персистентность HITL-запросов на диске."""

    def test_request_persists_to_disk(self, tmp_path):
        manager = HITLManager(
            profiles_dir=str(tmp_path / HITL_PROFILES_DIR),
            requests_dir=str(tmp_path / HITL_REQUESTS_DIR),
        )
        request = HITLRequest(
            request_id=HITL_REQUEST_ID_1,
            url=EXAMPLE_URL,
            status=HITL_STATUS_PENDING,
        )
        manager._persist_request(request)

        files = list((tmp_path / HITL_REQUESTS_DIR).glob(HITL_JSON_GLOB))
        assert len(files) == 1

    def test_requests_loaded_from_disk(self, tmp_path):
        requests_dir = tmp_path / HITL_REQUESTS_DIR
        manager = HITLManager(
            profiles_dir=str(tmp_path / HITL_PROFILES_DIR),
            requests_dir=str(requests_dir),
        )
        request = HITLRequest(
            request_id=HITL_REQUEST_ID_2,
            url=EXAMPLE_URL,
            status=HITL_STATUS_RESOLVED,
        )
        manager._persist_request(request)

        # Новый экземпляр с тем же каталогом загружает запросы с диска.
        manager2 = HITLManager(
            profiles_dir=str(tmp_path / HITL_PROFILES_DIR),
            requests_dir=str(requests_dir),
        )
        assert HITL_REQUEST_ID_2 in manager2._requests
        assert manager2._requests[HITL_REQUEST_ID_2].status == (
            HITL_STATUS_RESOLVED
        )

    @pytest.mark.asyncio
    async def test_check_status_restores_from_disk(self, tmp_path):
        requests_dir = tmp_path / HITL_REQUESTS_DIR
        manager = HITLManager(
            profiles_dir=str(tmp_path / HITL_PROFILES_DIR),
            requests_dir=str(requests_dir),
        )
        request = HITLRequest(
            request_id=HITL_REQUEST_ID_3,
            url=EXAMPLE_URL,
            status=HITL_STATUS_PENDING,
        )
        manager._persist_request(request)

        # Новый экземпляр без загрузки в память — check_status читает с диска.
        manager2 = HITLManager(
            profiles_dir=str(tmp_path / HITL_PROFILES_DIR),
            requests_dir=str(requests_dir),
        )
        manager2._requests.clear()  # имитируем отсутствие в памяти
        restored = await manager2.check_status(HITL_REQUEST_ID_3)
        assert restored.status == HITL_STATUS_PENDING
        assert restored.url == EXAMPLE_URL

    @pytest.mark.asyncio
    async def test_check_status_not_found(self, tmp_path):
        manager = HITLManager(
            profiles_dir=str(tmp_path / HITL_PROFILES_DIR),
            requests_dir=str(tmp_path / HITL_REQUESTS_DIR),
        )
        result = await manager.check_status(HITL_NONEXISTENT_ID)
        assert result.status == HITL_STATUS_NOT_FOUND
