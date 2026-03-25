from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {".py", ".md", ".json", ".spec", ".ini", ".toml", ".cfg", ".txt", ".yml", ".yaml"}
TEXT_FILENAMES = {".editorconfig", ".gitattributes", ".gitignore"}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", "artifacts", "build", "dist", "logs"}


def _tracked_text_files() -> list[Path]:
    output = ""
    try:
        output = subprocess.check_output(
            ["git", "-c", "core.quotepath=false", "ls-files"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        pytest.skip("git is required to enumerate tracked repository files")

    files: list[Path] = []
    for rel_path in output.splitlines():
        if not rel_path:
            continue
        path = ROOT / rel_path
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS or path.name in TEXT_FILENAMES:
            files.append(path)
    return sorted(files)


def test_tracked_text_files_are_utf8_decodable() -> None:
    for path in _tracked_text_files():
        path.read_text(encoding="utf-8")


def test_tracked_text_files_do_not_contain_replacement_characters() -> None:
    for path in _tracked_text_files():
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text, str(path.relative_to(ROOT))
