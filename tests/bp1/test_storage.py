from pathlib import Path
from typing import Any

from core.config import settings
from src.bp1.storage import RawDataService, copy_html_file


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value


def test_copy_html_file_skips_copy_when_source_is_destination(
    tmp_path: Path, monkeypatch
) -> None:
    html_path = tmp_path / 'snapshot.html'
    content = '<html><body>important snapshot</body></html>'
    html_path.write_text(content, encoding='utf-8')

    def fail_if_called(*args, **kwargs) -> None:
        raise AssertionError('shutil.copy2 must not run for the same file')

    monkeypatch.setattr('src.bp1.storage.shutil.copy2', fail_if_called)

    result = copy_html_file(str(html_path), str(tmp_path))

    assert result == str(html_path)
    assert html_path.read_text(encoding='utf-8') == content


def test_copy_html_file_copies_from_another_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / 'source'
    destination_dir = tmp_path / 'destination'
    source_dir.mkdir()
    source_path = source_dir / 'snapshot.html'
    content = '<html><body>classic parser snapshot</body></html>'
    source_path.write_text(content, encoding='utf-8')

    result = copy_html_file(str(source_path), str(destination_dir))

    destination_path = destination_dir / source_path.name
    assert result == str(destination_path)
    assert destination_path.read_text(encoding='utf-8') == content
    assert source_path.read_text(encoding='utf-8') == content


async def test_persist_keeps_self_saved_html_and_records_its_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, 'bp1_data_root', str(tmp_path))
    html_dir = Path(settings.bp1_html_dir)
    html_dir.mkdir(parents=True)
    html_path = html_dir / 'adaptive-snapshot.html'
    content = '<html><body>adaptive parser snapshot</body></html>'
    html_path.write_text(content, encoding='utf-8')

    redis = _FakeRedis()
    service = RawDataService(session=object(), redis_client=redis)
    saved_values: dict[str, Any] = {}

    async def fake_save_raw_item(**kwargs: Any) -> int:
        saved_values.update(kwargs)
        return 42

    monkeypatch.setattr(service, 'save_raw_item', fake_save_raw_item)

    result = await service.persist(
        search_task_id=7,
        response_data={'items': [{'title': 'Event'}]},
        html_source_path=str(html_path),
    )

    assert result['raw_item_id'] == 42
    assert result['html_file_path'] == str(html_path)
    assert saved_values['html_file_path'] == str(html_path)
    assert html_path.read_text(encoding='utf-8') == content
    assert html_path.stat().st_size > 0
