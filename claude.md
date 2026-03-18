# 🤖 Claude AI Development Intelligence: Internal Regulation Searcher v9.3

This file tracks architecture and maintenance rules after modularization and follow-up hardening/refinement.

---

## 🧱 Module Topology

| Module | Responsibility |
| :--- | :--- |
| `regfinder/app_types.py` | Shared config/constants/enums/dataclasses |
| `regfinder/runtime.py` | Import helpers, logging, op_id, path policy |
| `regfinder/persistence.py` | Config migration + JSON stores (bookmarks/recents/search logs) |
| `regfinder/model_inventory.py` | Downloaded-model state and size cache |
| `regfinder/worker_registry.py` | Worker lifecycle registry by task key |
| `regfinder/file_utils.py` | File I/O helpers + scandir discovery + lazy encoding fallback |
| `regfinder/document_extractor.py` | TXT/DOCX/PDF/HWP extraction (+PDF password/OCR hook) |
| `regfinder/text_cache.py` | Text cache (SQLite) |
| `regfinder/bm25.py` | BM25Index tokenizer/ranker with postings |
| `regfinder/qa_system.py` | Core indexing/search/text-cache+vector-cache service |
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
- `CACHE_SCHEMA_VERSION=3`
- `CONFIG_SCHEMA_VERSION=2`
- data root: portable app directory first, then `LOCALAPPDATA/APPDATA`
- text/vector cache root: tempdir `reg_qa_v93/text`, `reg_qa_v93/vector`

---

## 🔎 Functional Notes

- Search supports extension/filename/path filters.
- Search supports sorting by score/filename/mtime.
- Bookmark save/export and multi recent-folder list supported.
- Diagnostic tab includes index status + search log summary.
- Error dialogs include error-code-specific recovery guide text.
- Empty-state cards use dedicated object names/styles to avoid label background bleed-through.
- Frozen onefile model download uses in-process fallback and validates `Pillow`, `scikit-learn`, `sentence_transformers` before loading embeddings.
- Text cache is reused across model switches; vector cache is model-specific.
- `FileUtils.safe_read()` uses `UTF-8 -> CP949 -> EUC-KR` fast path and lazily imports `charset_normalizer` only on fallback.
- Search input becomes enabled immediately after successful model load, even before folder indexing.
- Settings model selector surfaces download status and prioritizes downloaded models using Hugging Face cache directory detection.
- Model download state access is strongly typed via `ModelDownloadState`, preventing Pylance drift in selector/status UI.
- Cache usage display is refreshed via worker and model download state is cached in `model_inventory.json`.

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

## 🧰 Repository Assets

- `pyrightconfig.json`: repo-wide Pylance/Pyright baseline
- `.editorconfig`: UTF-8, LF, whitespace policy
- `.gitattributes`: tracked text file line-ending normalization
- `.vscode/settings.json`: workspace UTF-8/Pylance/Python terminal defaults
- `tests/test_repo_text_encoding.py`: tracked text-file UTF-8/replacement-char regression test

---

## 📦 Build Notes (PyInstaller)

- Entry script: `사내 규정검색기 v9 PyQt6.py`
- Onefile name: `사내 규정검색기 v9.3_onefile`
- Spec hiddenimports includes additional internal modules:
  - `regfinder.persistence`
  - `regfinder.text_cache`
  - `regfinder.model_inventory`
  - `regfinder.worker_registry`
  - `regfinder.main_window_ui_mixin`
  - `regfinder.main_window_mixins`
  - `regfinder.qa_system_mixins`
- Spec also bundles runtime metadata required for offline embeddings:
  - `sentence-transformers`
  - `scikit-learn`
  - `pillow`
- Spec keeps `charset_normalizer` hiddenimports because encoding fallback is loaded dynamically.
- Spec excludes dev-only tooling such as `pytest`, `pyright`, `mypy`
- Do not exclude `PIL` / `Pillow` or `scikit-learn` while slimming the EXE; packaged `sentence_transformers` import path depends on them.

---

## ✅ Validation Gates

- `pyright .`
- `python tools/smoke_refactor.py`
- `python tools/benchmark_performance.py`
- `python -m py_compile "사내 규정검색기 v9 PyQt6.spec"`
- `python -m unittest discover -s tests -v`
- `python -m pytest -q`
- tracked text files should remain `UTF-8` without BOM
- Windows PowerShell/Python mojibake can be a display issue rather than committed file corruption
