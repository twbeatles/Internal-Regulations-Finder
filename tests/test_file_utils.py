import os

from regfinder import file_utils as file_utils_module
from regfinder.file_utils import FileUtils


def test_get_metadata_returns_size_and_mtime(tmp_path):
    fp = tmp_path / "sample.txt"
    fp.write_text("abc", encoding="utf-8")

    meta = FileUtils.get_metadata(str(fp))

    assert meta is not None
    assert meta["size"] == 3
    assert "mtime" in meta


def test_open_file_windows_calls_startfile(monkeypatch, tmp_path):
    called = {}

    monkeypatch.setattr(file_utils_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        file_utils_module.os,
        "startfile",
        lambda path: called.setdefault("path", path),
        raising=False,
    )

    FileUtils.open_file(str(tmp_path))

    assert called["path"] == str(tmp_path)
