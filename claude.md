# 🤖 Claude AI Development Intelligence: Internal Regulation Searcher v9.3 (Modular)

This document describes the **post-refactor modular architecture** and maintenance rules for the project.

---

## 🧱 Module Topology

| Module | Responsibility |
| :--- | :--- |
| `regfinder/app_types.py` | Shared config, enums, dataclasses (`AppConfig`, `TaskResult`, `FileInfo`) |
| `regfinder/runtime.py` | Import helpers, logging, operation IDs, portable-first path policy |
| `regfinder/file_utils.py` | File I/O helpers and metadata utilities |
| `regfinder/bm25.py` | Lightweight BM25 tokenizer/ranker |
| `regfinder/document_extractor.py` | TXT/DOCX/PDF/HWP extraction |
| `regfinder/qa_system.py` | Core indexing/search/cache/diagnostics service |
| `regfinder/workers.py` | Worker threads and cancellation model |
| `regfinder/ui_style.py` | QSS stylesheet (`DARK_STYLE`) |
| `regfinder/ui_components.py` | Reusable widgets (`ResultCard`, `ProgressDialog`, etc.) |
| `regfinder/main_window.py` | Main UI orchestration and user interaction flow |
| `regfinder/app_main.py` | QApplication bootstrap and main entry |
| `사내 규정검색기 v9 PyQt6.py` | Backward-compatible wrapper entry |

---

## ⚙️ Core Configuration Snapshot

| Constant | Value | Purpose |
| :--- | :--- | :--- |
| `CHUNK_SIZE` | 800 | Chunk size for Korean-heavy documents |
| `CHUNK_OVERLAP` | 80 | Context overlap between chunks |
| `VECTOR_WEIGHT` | 0.7 | Semantic retrieval weight |
| `BM25_WEIGHT` | 0.3 | Keyword retrieval weight |
| `DEFAULT_FONT_SIZE` | 14 | Default UI readability baseline |

---

## 🧠 Retrieval & Cache Behavior

### Incremental indexing
- Cache key uses model hash + folder hash.
- File-level change detection uses `size` and `mtime`.
- Supports add/modify/delete detection.
- Falls back to full rebuild when partial update is unsafe.

### Cache storage and integrity
- Cache root: `tempfile.gettempdir()/reg_qa_v90`.
- Schema validation (`CACHE_SCHEMA_VERSION`) enforced before load.
- Corrupted cache is removed automatically and rebuilt.

### Hybrid ranking
- Vector and BM25 scores are normalized independently.
- Final score = `VECTOR_WEIGHT * vec + BM25_WEIGHT * bm25`.

---

## 🌐 Offline & Diagnostics

- Offline model download via `ModelDownloadThread` with selectable models.
- Download timeout: `HF_HUB_DOWNLOAD_TIMEOUT = 300`.
- Persistent model path: `get_models_directory()`.
- Diagnostic export creates a zip with environment/config/log/cache summary (no raw document content).
- Errors expose `TaskResult.debug` through “상세 보기”.

---

## 🧵 Threading Rules (must preserve)

1. Never update UI widgets inside `run()`.
2. Use Qt signals to send results/progress back to UI thread.
3. Support cancellation via `cancel()` / `is_canceled()`.
4. Release thread/widget objects with `deleteLater()` and clear references (`worker = None`).

---

## 🛠️ Refactor Validation Assets

| Artifact | Purpose |
| :--- | :--- |
| `tools/symbol_inventory.py` | Symbol extraction and before/after diff |
| `tools/smoke_refactor.py` | Compile/import/sanity smoke checks |
| `artifacts/symbols_before.json` | Pre-refactor symbol baseline |
| `artifacts/symbols_after.json` | Post-refactor symbol snapshot |
| `docs/refactor_mapping.md` | Old-to-new module mapping |
| `docs/refactor_checklist.md` | Manual verification checklist |

---

## 📦 Build Notes (PyInstaller)

- Onefile output remains `dist/사내 규정검색기 v9.3_onefile.exe`.
- Entry script remains `사내 규정검색기 v9 PyQt6.py` for compatibility.
- Spec explicitly includes `regfinder.*` hidden imports and project root in `pathex`.

---

## ✅ Safe Fix Included in Refactor

- `MainWindow._update_internal_state_display` now aligns with actual operation fields:
  - prefers `kind` over legacy `type`
  - derives status from `success` when available
