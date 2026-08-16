"""Тесты для src/bp1/raw_storage/ — дедупликация Bronze Layer (Шаг 7)."""

from datetime import datetime

import pytest

from src.bp1.raw_storage.backends.disk_backend import DiskBackend
from src.bp1.raw_storage.core.deduplication import ContentHashDeduplicator
from src.bp1.raw_storage.core.models import MetaInfo, RawDataFile, RawDataItem
from src.bp1.raw_storage.services.repository import RawDataRepository
from src.bp1.raw_storage.utils.hashing import compute_items_hash


def _make_file(
    *, search_task_id: int = 1, url: str = 'https://x.ru/1'
) -> RawDataFile:
    return RawDataFile(
        meta=MetaInfo(
            search_task_id=search_task_id,
            source='x.ru',
            competitor='ООО Тест',
            trigger='trigger',
            source_request_url='https://x.ru/search?q=test',
            fetched_at=datetime(2026, 1, 1),
        ),
        items=[
            RawDataItem(url=url, title='Заголовок', text='Текст новости'),
        ],
    )


# ============================================================================
# compute_items_hash
# ============================================================================


def test_compute_items_hash_same_content_same_hash():
    """Одинаковое содержимое items даёт одинаковый хеш."""
    items = [{'url': 'https://x.ru/1', 'title': 'T', 'text': 'body'}]
    assert compute_items_hash(items) == compute_items_hash(items)


def test_compute_items_hash_different_content_different_hash():
    """Разное содержимое items даёт разный хеш."""
    a = [{'url': 'https://x.ru/1', 'title': 'T', 'text': 'body'}]
    b = [{'url': 'https://x.ru/2', 'title': 'T', 'text': 'body'}]
    assert compute_items_hash(a) != compute_items_hash(b)


def test_compute_items_hash_key_order_independent():
    """Порядок ключей внутри dict не влияет на хеш (sort_keys=True)."""
    a = [{'url': 'https://x.ru/1', 'title': 'T'}]
    b = [{'title': 'T', 'url': 'https://x.ru/1'}]
    assert compute_items_hash(a) == compute_items_hash(b)


# ============================================================================
# ContentHashDeduplicator
# ============================================================================


@pytest.mark.asyncio
async def test_content_hash_deduplicator_true_when_found():
    """is_duplicate() возвращает True, если lookup нашёл путь."""

    async def _find(_hash: str) -> str | None:
        return '/some/path.json'

    dedup = ContentHashDeduplicator(_find)
    assert await dedup.is_duplicate('anyhash') is True


@pytest.mark.asyncio
async def test_content_hash_deduplicator_false_when_not_found():
    """is_duplicate() возвращает False, если lookup ничего не нашёл."""

    async def _find(_hash: str) -> str | None:
        return None

    dedup = ContentHashDeduplicator(_find)
    assert await dedup.is_duplicate('anyhash') is False


# ============================================================================
# RawDataRepository + DiskBackend (интеграция, файловая система, tmp_path)
# ============================================================================


@pytest.mark.asyncio
async def test_save_identical_content_does_not_duplicate(tmp_path):
    """Повторное сохранение идентичного по содержимому файла не создаёт
    вторую запись — возвращает путь к уже существующему файлу."""
    backend = DiskBackend(base_path=str(tmp_path))
    repo = RawDataRepository(storage_backend=backend)

    first = _make_file()
    second = _make_file()  # тот же search_task_id/items, но свой raw_id

    path_a = await repo.save(first)
    path_b = await repo.save(second)

    assert path_a == path_b
    assert len(await backend.list('')) == 1


@pytest.mark.asyncio
async def test_save_different_content_creates_separate_files(tmp_path):
    """Разное содержимое items сохраняется как отдельные файлы."""
    backend = DiskBackend(base_path=str(tmp_path))
    repo = RawDataRepository(storage_backend=backend)

    path_a = await repo.save(_make_file(url='https://x.ru/1'))
    path_b = await repo.save(_make_file(url='https://x.ru/2'))

    assert path_a != path_b
    assert len(await backend.list('')) == 2


@pytest.mark.asyncio
async def test_find_by_content_hash_returns_none_when_missing(tmp_path):
    """find_by_content_hash возвращает None, а не бросает исключение."""
    backend = DiskBackend(base_path=str(tmp_path))
    repo = RawDataRepository(storage_backend=backend)

    assert await repo.find_by_content_hash('nonexistent') is None
