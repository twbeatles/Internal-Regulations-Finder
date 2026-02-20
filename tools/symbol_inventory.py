#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Dict, Iterable, List, Set


def iter_python_files(paths: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file() and p.suffix == ".py":
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(x for x in p.rglob("*.py") if x.is_file()))
    dedup = sorted({f.resolve() for f in files})
    return dedup


def collect_symbols(py_file: Path) -> Dict[str, List[str]]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    symbols: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            symbols.append(f"func:{node.name}")
        elif isinstance(node, ast.ClassDef):
            symbols.append(f"class:{node.name}")
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    symbols.append(f"method:{node.name}.{item.name}")
    return {"file": str(py_file), "symbols": sorted(symbols)}


def read_symbol_set(path: Path) -> Set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("symbols", []))


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and compare Python symbol inventory.")
    parser.add_argument("--paths", nargs="+", required=True, help="Files or directories to scan.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--compare-before", help="Optional previous inventory JSON.")
    parser.add_argument("--compare-after", help="Optional current inventory JSON.")
    args = parser.parse_args()

    files = iter_python_files(args.paths)
    per_file = [collect_symbols(f) for f in files]
    merged: Set[str] = set()
    for item in per_file:
        merged.update(item["symbols"])

    out_obj = {
        "count": len(merged),
        "files": [str(f) for f in files],
        "symbols": sorted(merged),
        "per_file": per_file,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[symbol_inventory] wrote: {out_path} ({len(merged)} symbols)")

    if args.compare_before and args.compare_after:
        before = read_symbol_set(Path(args.compare_before))
        after = read_symbol_set(Path(args.compare_after))
        missing = sorted(before - after)
        added = sorted(after - before)
        print(f"[symbol_inventory] missing={len(missing)} added={len(added)}")
        if missing:
            for item in missing:
                print(f"  MISSING: {item}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
