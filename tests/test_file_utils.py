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


def test_safe_read_uses_fast_path_without_charset_normalizer(monkeypatch, tmp_path):
    fp = tmp_path / "utf8.txt"
    fp.write_text("사내 규정 테스트", encoding="utf-8")

    def fail_on_charset_normalizer(name: str):
        if name == "charset_normalizer":
            raise AssertionError("charset_normalizer should not be imported for utf-8 fast path")
        return object()

    monkeypatch.setattr(file_utils_module.importlib, "import_module", fail_on_charset_normalizer)

    text, error = FileUtils.safe_read(str(fp))

    assert error is None
    assert text == "사내 규정 테스트"


def test_safe_read_falls_back_to_charset_normalizer(monkeypatch, tmp_path):
    fp = tmp_path / "fallback.bin"
    fp.write_bytes(b"\xff\xfe\x00\xd8")
    called = {"charset": False}

    class _FakeMatch:
        encoding = "utf-16"

    class _FakeResults:
        @staticmethod
        def best():
            return _FakeMatch()

    class _FakeCharsetNormalizer:
        @staticmethod
        def from_bytes(raw: bytes):
            called["charset"] = True
            assert raw == b"\xff\xfe\x00\xd8"
            return _FakeResults()

    def fake_import_module(name: str):
        if name == "charset_normalizer":
            return _FakeCharsetNormalizer()
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(file_utils_module.importlib, "import_module", fake_import_module)

    text, error = FileUtils.safe_read(str(fp))

    assert error is None
    assert called["charset"] is True
    assert isinstance(text, str)


def test_discover_files_skips_permission_denied_subtree(monkeypatch, tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    allowed = root / "allowed.txt"
    allowed.write_text("ok", encoding="utf-8")
    blocked = root / "blocked"
    blocked.mkdir()

    original_scandir = file_utils_module.os.scandir

    def fake_scandir(path: str):
        if os.path.normpath(path) == os.path.normpath(str(blocked)):
            raise PermissionError("denied")
        return original_scandir(path)

    monkeypatch.setattr(file_utils_module.os, "scandir", fake_scandir)

    skipped_paths: list[str] = []
    discovered = FileUtils.discover_files(
        str(root),
        recursive=True,
        supported_extensions=(".txt",),
        skipped_paths=skipped_paths,
    )

    assert [item.name for item in discovered] == ["allowed.txt"]
    assert skipped_paths == [os.path.normpath(str(blocked))]
