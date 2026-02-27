# 🤖 Claude AI Development Intelligence: Internal Regulation Searcher v9.3

This file tracks architecture and maintenance rules after modularization and follow-up hardening/refinement.

---

## 🧱 Module Topology

| Module | Responsibility |
| :--- | :--- |
| `regfinder/app_types.py` | Shared config/constants/enums/dataclasses |
| `regfinder/runtime.py` | Import helpers, logging, op_id, path policy |
| `regfinder/persistence.py` | Config migration + JSON stores (bookmarks/recents/search logs) |
| `regfinder/worker_registry.py` | Worker lifecycle registry by task key |
| `regfinder/file_utils.py` | File I/O helpers |
| `regfinder/document_extractor.py` | TXT/DOCX/PDF/HWP extraction (+PDF password/OCR hook) |
| `regfinder/bm25.py` | BM25 tokenizer/ranker |
| `regfinder/qa_system.py` | Core indexing/search/cache service |
| `regfinder/qa_system_mixins.py` | Diagnostics export, cache/index status APIs |
| `regfinder/workers.py` | Worker threads and cancellation |
| `regfinder/ui_style.py` | QSS stylesheet |
| `regfinder/ui_components.py` | Reusable widgets |
| `regfinder/main_window.py` | Main orchestration/event flow |
| `regfinder/main_window_ui_mixin.py` | UI builder methods |
| `regfinder/main_window_mixins.py` | Config/diagnostics/bookmark UI logic |
| `regfinder/app_main.py` | QApplication bootstrap |

---

## ⚙️ Runtime Snapshot

- `CHUNK_SIZE=800`, `CHUNK_OVERLAP=80`
- `VECTOR_WEIGHT=0.7`, `BM25_WEIGHT=0.3`
- `CACHE_SCHEMA_VERSION=2`
- `CONFIG_SCHEMA_VERSION=2`
- cache root: `tempfile.gettempdir()/reg_qa_v90`

---

## 🔎 Functional Notes

- Search supports extension/filename/path filters.
- Search supports sorting by score/filename/mtime.
- Bookmark save/export and multi recent-folder list supported.
- Diagnostic tab includes index status + search log summary.
- Error dialogs include error-code-specific recovery guide text.

---

## 🧵 Threading Rules

1. Never update UI from worker `run()`.
2. Use Qt signals for all progress/result updates.
3. Support cancellation with `cancel()` / `is_canceled()`.
4. Release workers via `deleteLater()`.
5. Manage workers by key (`WorkerRegistry`) instead of a single slot.

---

## 📄 Extraction Notes

- `check_pdf_encrypted()` is available before indexing.
- Password-protected PDFs require user password; password is session-memory only.
- OCR hook exists via `BaseOCREngine`; default is `NoOpOCREngine`.
- HWP extraction prioritizes `BodyText/Section*` and supports raw-deflate streams.

---

## 📦 Build Notes (PyInstaller)

- Entry script: `사내 규정검색기 v9 PyQt6.py`
- Onefile name: `사내 규정검색기 v9.3_onefile`
- Spec hiddenimports includes additional internal modules:
  - `regfinder.persistence`
  - `regfinder.worker_registry`
  - `regfinder.main_window_ui_mixin`
  - `regfinder.main_window_mixins`
  - `regfinder.qa_system_mixins`

---

## ✅ Validation

- `python tools/smoke_refactor.py`
- `python -m unittest discover -s tests -v`
- `pytest -q`
