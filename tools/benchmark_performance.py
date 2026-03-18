#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def measure_ms(fn: Callable[[], Any], *, repeat: int = 1) -> dict[str, Any]:
    samples: list[float] = []
    result: Any = None
    for _ in range(max(1, repeat)):
        started = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - started) * 1000.0)
    return {
        "samples_ms": [round(sample, 2) for sample in samples],
        "avg_ms": round(sum(samples) / len(samples), 2),
        "result": result,
    }


def benchmark_startup() -> dict[str, Any]:
    script = (
        "import sys,time;"
        f"sys.path.insert(0, {str(ROOT)!r});"
        "t=time.perf_counter();"
        "import regfinder.app_main;"
        "print((time.perf_counter()-t)*1000)"
    )
    samples: list[float] = []
    for _ in range(3):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        samples.append(float((completed.stdout or "0").strip() or "0"))
    return {
        "samples_ms": [round(sample, 2) for sample in samples],
        "avg_ms": round(sum(samples) / len(samples), 2),
        "result": "regfinder.app_main",
    }


def benchmark_import_core() -> dict[str, Any]:
    modules = [
        "regfinder.runtime",
        "regfinder.file_utils",
        "regfinder.text_cache",
        "regfinder.model_inventory",
        "regfinder.qa_system",
        "regfinder.main_window",
    ]

    script = (
        "import importlib,sys,time;"
        f"sys.path.insert(0, {str(ROOT)!r});"
        f"mods={modules!r};"
        "t=time.perf_counter();"
        "[importlib.import_module(mod) for mod in mods];"
        "print((time.perf_counter()-t)*1000)"
    )
    samples: list[float] = []
    for _ in range(3):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        samples.append(float((completed.stdout or "0").strip() or "0"))
    return {
        "samples_ms": [round(sample, 2) for sample in samples],
        "avg_ms": round(sum(samples) / len(samples), 2),
        "result": len(modules),
    }


def benchmark_discover(folder: Path, recursive: bool) -> dict[str, Any]:
    from regfinder.app_types import AppConfig
    from regfinder.file_utils import FileUtils

    def _run():
        files = FileUtils.discover_files(
            str(folder),
            recursive=recursive,
            supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
        )
        return len(files)

    return measure_ms(_run, repeat=3)


def benchmark_decode(file_path: Path) -> dict[str, Any]:
    from regfinder.file_utils import FileUtils

    def _run():
        text, error = FileUtils.safe_read(str(file_path))
        if error:
            raise RuntimeError(error)
        return len(text)

    return measure_ms(_run, repeat=20)


def benchmark_index_and_search(folder: Path, model_name: str, secondary_model: str | None) -> dict[str, Any]:
    from regfinder.app_types import AppConfig
    from regfinder.file_utils import FileUtils
    from regfinder.qa_system import RegulationQASystem

    files = FileUtils.discover_files(
        str(folder),
        recursive=True,
        supported_extensions=AppConfig.SUPPORTED_EXTENSIONS,
    )
    if not files:
        raise RuntimeError("benchmark folder has no supported files")

    qa = RegulationQASystem()

    def _load_model(name: str) -> None:
        result = qa.load_model(name)
        if not result.success:
            raise RuntimeError(result.message)

    def _index() -> int:
        result = qa.process_documents(str(folder), files, lambda *_: None)
        if not result.success:
            raise RuntimeError(result.message)
        return int((result.data or {}).get("chunks", 0) or 0)

    def _search() -> int:
        result = qa.search("규정", k=3, hybrid=True)
        if not result.success:
            raise RuntimeError(result.message)
        return len(result.data or [])

    load_model = measure_ms(lambda: _load_model(model_name))
    index_cold = measure_ms(_index)
    index_warm = measure_ms(_index)
    search = measure_ms(_search, repeat=5)

    model_switch = None
    if secondary_model and secondary_model != model_name:
        model_switch = measure_ms(lambda: _load_model(secondary_model))
        model_switch["follow_up_index"] = measure_ms(_index)

    qa.cleanup()
    return {
        "model_name": model_name,
        "load_model": load_model,
        "index_cold": index_cold,
        "index_warm": index_warm,
        "search": search,
        "model_switch": model_switch,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Internal Regulations Finder performance paths")
    parser.add_argument("--folder", type=Path, help="benchmark target folder")
    parser.add_argument("--recursive", action="store_true", help="use recursive discovery")
    parser.add_argument("--decode-file", type=Path, help="single file for TXT decode benchmark")
    parser.add_argument("--model-name", default="JHGan SBERT (빠름)", help="primary model name")
    parser.add_argument("--secondary-model", help="optional model for model-switch benchmark")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "startup": benchmark_startup(),
        "import_core": benchmark_import_core(),
    }
    if args.folder:
        report["discover"] = benchmark_discover(args.folder, args.recursive)
        report["index_search"] = benchmark_index_and_search(args.folder, args.model_name, args.secondary_model)
    if args.decode_file:
        report["decode"] = benchmark_decode(args.decode_file)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
