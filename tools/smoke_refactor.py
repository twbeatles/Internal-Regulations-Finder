#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import json
import py_compile
import sys
from pathlib import Path
from typing import List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def compile_targets() -> None:
    targets: List[Path] = []
    targets.extend((ROOT / "regfinder").rglob("*.py"))
    targets.append(next(ROOT.glob("*PyQt6.py")))
    for target in sorted(targets):
        py_compile.compile(str(target), doraise=True)
    print(f"[smoke] py_compile ok ({len(targets)} files)")


def import_targets() -> None:
    modules = [
        "regfinder.app_types",
        "regfinder.runtime",
        "regfinder.persistence",
        "regfinder.worker_registry",
        "regfinder.main_window_ui_mixin",
        "regfinder.main_window_mixins",
        "regfinder.qa_system_mixins",
        "regfinder.file_utils",
        "regfinder.bm25",
        "regfinder.document_extractor",
        "regfinder.qa_system",
        "regfinder.workers",
        "regfinder.ui_style",
        "regfinder.ui_components",
        "regfinder.main_window",
        "regfinder.app_main",
    ]
    for mod in modules:
        importlib.import_module(mod)
    print(f"[smoke] import ok ({len(modules)} modules)")


def symbol_diff_check() -> None:
    before_path = ROOT / "artifacts" / "symbols_before.json"
    after_path = ROOT / "artifacts" / "symbols_after.json"
    if not before_path.exists() or not after_path.exists():
        print("[smoke] symbol diff skipped (missing artifacts)")
        return
    before = set(json.loads(before_path.read_text(encoding="utf-8")).get("symbols", []))
    after = set(json.loads(after_path.read_text(encoding="utf-8")).get("symbols", []))
    missing = sorted(before - after)
    added = sorted(after - before)
    print(f"[smoke] symbol diff: missing={len(missing)} added={len(added)}")
    if missing:
        for item in missing:
            print(f"  MISSING: {item}")
        raise RuntimeError("symbol mismatch detected")


def sanity_checks() -> None:
    from regfinder.app_types import AppConfig
    from regfinder.main_window import MainWindow
    from regfinder.qa_system import RegulationQASystem
    from regfinder.runtime import get_data_directory, get_models_directory

    qa = RegulationQASystem()
    assert isinstance(AppConfig.APP_VERSION, str)
    assert callable(get_data_directory)
    assert callable(get_models_directory)
    assert hasattr(qa, "process_documents")
    assert hasattr(qa, "search")
    assert MainWindow.__name__ == "MainWindow"
    print("[smoke] sanity checks ok")


def main() -> int:
    compile_targets()
    import_targets()
    symbol_diff_check()
    sanity_checks()
    print("[smoke] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
