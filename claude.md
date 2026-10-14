# 🤖 Claude AI Development Intelligence: Internal Regulation Searcher v9.3

This file tracks architecture and maintenance rules after modularization and follow-up hardening/refinement.

---

## 🧱 Module Topology

| Module | Responsibility |
| :--- | :--- |
| `regfinder/core/types.py` | Shared config/constants/enums/dataclasses |
| `regfinder/core/runtime.py` | Import helpers, logging, op_id, path policy |
| `regfinder/core/file_utils.py` | File I/O helpers + scandir discovery + lazy encoding fallback |
| `regfinder/storage/persistence.py` | Config migration + JSON stores (bookmarks/recents/search logs) |
| `regfinder/storage/text_cache.py` | Text cache (SQLite, fingerprints, page metadata) |
| `regfinder/storage/model_inventory.py` | Downloaded-model state and size cache |
| `regfinder/documents/extractor.py` | TXT/DOCX/PDF/HWP/HWPX extraction (+PDF page metadata/optional Tesseract OCR) |
| `regfinder/search/text.py` | Shared search normalization/token expansion/filter matching |
| `regfinder/search/bm25.py` | BM25Index tokenizer/ranker with postings |
| `regfinder/search/qa_system.py` | Core indexing/search/text-cache+vector-cache service |
| `regfinder/search/diagnostics.py` | Diagnostics export, cache/index status APIs |
| `regfinder/application/workers.py` | Worker threads and cancellation |
| `regfinder/application/worker_registry.py` | Worker lifecycle registry by task key |
| `regfinder/application/app_main.py` | QApplication bootstrap |
| `regfinder/ui/style.py` | QSS stylesheet |
| `regfinder/ui/components.py` | Reusable widgets |
| `regfinder/ui/main_window.py` | Main orchestration/event flow |
| `regfinder/ui/window_builder.py` | UI builder methods |
| `regfinder/ui/window_mixins.py` | Config/diagnostics/bookmark UI logic |
| `regfinder/*.py` compatibility wrappers | Preserve legacy import paths while aliasing to the feature packages |

---

## ⚙️ Runtime Snapshot

- `CHUNK_SIZE=800`, `CHUNK_OVERLAP=80`
- `VECTOR_WEIGHT=0.7`, `BM25_WEIGHT=0.3`
- `CACHE_SCHEMA_VERSION=4`
- `CONFIG_SCHEMA_VERSION=4`
- `MAX_FILTERED_VECTOR_FETCH=1000`
- `MAX_DOCS_IN_MEMORY=5000` is a soft warning threshold, not a hard stop
- data root: portable app directory first, then `LOCALAPPDATA/APPDATA`
- text/vector cache root: tempdir `reg_qa_v93/text`, `reg_qa_v93/vector`
- text cache file rows store a file fingerprint in addition to size/mtime for stale-cache safety

---

## 🔎 Functional Notes

- Search supports extension/filename/path filters and sorting by `score_desc`, `filename_asc`, `mtime_desc`.
- Search normalization is centralized in `regfinder.search.text`, so BM25, filter matching, and UI highlighting share the same semantics.
- Korean no-space queries such as `휴가규정` are expanded with char n-grams, and simple particles like `을/를/은/는` are stripped for semantic matching.
- Search results are grouped at file level, not chunk level.
  - The representative snippet comes from the highest-ranked chunk.
  - Each result carries `match_count`, `snippet_chunk_idx`, `matched_chunk_indices`, `matched_doc_ids`.
- Result score wording is `랭킹 점수`, not a literal similarity percentage.
- Filtered vector search increases `fetch_k` progressively up to `MAX_FILTERED_VECTOR_FETCH`, reducing false negatives behind the initial window and reporting `vector_limit_reached` when capped.
- BM25 search expands the candidate chunk pool until enough distinct file-level results can be returned.
- BM25 is built from content plus repeated filename text for lightweight title boost.
- Document processing builds BM25 first, then attempts vector sync.
  - If vector cache build/load fails, the app remains searchable in `bm25_only` mode.
  - GUI search entry stays available only when a searchable index exists; model-only state keeps the whole search panel disabled.
  - Canceling vector sync raises the document outcome `DOCS_CANCELED` and restores the previous searchable state.
  - Loading a model after a BM25-only folder index attempts vector cache creation in the same worker path to promote the index to hybrid mode.
- Search shows an inline progress card with cancel, keeps previous results visible until replacement, and surfaces active filters/sort/mode in the result header.
- No-result state can surface filter summary plus `필터 초기화`.
- Search history stores `q + filters + sort_by + k + hybrid` and restoring a history item replays the search immediately.
- Result detail uses a modal dialog with file open, path copy, evidence chunk navigation, and full indexed-document view.
- Result card font size updates live when the settings slider changes.
- File/bookmark numeric columns use numeric sort items rather than plain string table items.
- Modified-file re-extraction failures purge the previous cached text/chunks for that file, so stale content does not remain searchable.
- Encrypted PDFs are pre-scanned before folder indexing and file-level passwords are kept in session memory only.
- UI highlighting uses `highlight_spans()` from `regfinder.search.text`, so no-space Korean queries and particle stripping apply to visible highlight ranges too.
- Diagnostics expose `search_mode`, `vector_ready`, `memory_warning`, `vector_limit_reached`, text-cache path, file count, and chunk count through last-search stats, last operation, and index status, including model-less BM25-only state.
- Diagnostics ZIP export excludes `text_cache.sqlite` by default; it is included only for explicit one-time UI export.
- Settings include `keep_search_text` plus optional OCR fields through config schema v4 migration and invalid values are safely coerced back to defaults.
- Empty-state cards use dedicated object names/styles to avoid label background bleed-through.
- Frozen onefile model download uses in-process fallback and validates `Pillow`, `scikit-learn`, `sentence_transformers` before loading embeddings.
- Frozen onefile download cancel is deferred: the current model may finish before the worker stops.
- Results/bookmarks CSV exports use Python `csv` writer escaping, and cache clear resets memory state plus session PDF passwords while keeping the loaded model when available.
- Text cache is reused across model switches; vector cache is model-specific.
- `FileUtils.safe_read()` uses `UTF-8 -> CP949 -> EUC-KR` fast path and lazily imports `charset_normalizer` only on fallback.
- Folder loading can begin before a model is loaded; initial indexing may stay in `bm25_only` until embeddings are available.
- Folder scan skips permission-denied subtrees, records skipped paths, and surfaces them back to the UI as notices.
- OCR settings are persisted in config and the extractor can append OCR text for image or mixed PDFs when optional Tesseract dependencies are available.
- PDF extraction emits page-level segments so chunks/results/bookmarks/detail/export can carry `page_start` and `page_end`.
- HWPX extraction reads ZIP/XML content from section/header/footer XML files.
- Canceling or failing a folder load restores the previous in-memory index state instead of leaving mixed folder/runtime state behind.
- Search history deduplicates by full search context (`q + filters + sort_by + k + hybrid`), not by query string alone.
- Application shutdown now requests cancellation, waits briefly for workers, and blocks window close if a worker does not stop in time.
- Settings model selector surfaces download status and prioritizes downloaded models using Hugging Face cache directory detection.
- Startup skips automatic model load when the selected model snapshot is incomplete, leaving BM25 folder loading available.
- Model download state access is strongly typed via `ModelDownloadState`, preventing Pylance drift in selector/status UI.
- Cache usage display is refreshed via worker and model download state is cached in `model_inventory.json`.
- Logger setup falls back to a workspace-local log directory if the preferred log directory is not writable, which keeps tests/tooling from failing on import.

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
- `TesseractOCREngine` lazy-imports `fitz`, `pytesseract`, and Pillow image loading, uses `kor+eng` by default, and applies configured `tesseract_cmd` when present.
- Missing OCR Python packages or external Tesseract binary should produce a clear user-facing fallback message, not prevent normal indexing.
- HWP extraction prioritizes `BodyText/Section*` and supports raw-deflate streams.
- HWPX extraction reads XML text from the zipped document package.

---

## 🧰 Repository Assets

- `pyrightconfig.json`: repo-wide Pylance/Pyright baseline, with optional dependency missing-import noise suppressed
- `.editorconfig`: UTF-8, LF, whitespace policy
- `.gitattributes`: tracked text file line-ending normalization
- `.vscode/settings.json`: workspace UTF-8/Pylance/Python terminal defaults
- `.gitignore`: local test/temp/log folders such as `.pytest_localappdata/` and `.regfinder_logs/` are excluded
- `tests/test_repo_text_encoding.py`: tracked text-file UTF-8/replacement-char regression test

---

## 📦 Build Notes (PyInstaller)

- Entry script: `사내 규정검색기 v9.py`
- Onefile name: `사내 규정검색기 v9.3_onefile`
- Spec hiddenimports includes compatibility modules plus implementation packages:
  - `regfinder.core.*`
  - `regfinder.storage.*`
  - `regfinder.documents.*`
  - `regfinder.search.*`
  - `regfinder.application.*`
  - `regfinder.ui.*`
  - optional OCR modules `pytesseract` and `fitz`
- Spec also bundles runtime metadata required for offline embeddings:
  - `sentence-transformers`
  - `scikit-learn`
  - `pillow`
- Spec keeps `charset_normalizer` hiddenimports because encoding fallback is loaded dynamically.
- Spec excludes dev-only tooling such as `pytest`, `pyright`, `mypy`.
- Do not exclude `PIL` / `Pillow` or `scikit-learn` while slimming the EXE; packaged `sentence_transformers` import path depends on them.
- Optional OCR still requires an external Tesseract executable and installed language data; bundling Python imports alone is not sufficient.
- 2026-04-28 functional hardening added HWPX, PDF page metadata, diagnostics privacy mode, and optional Tesseract OCR wiring.

---

## ✅ Validation Gates

- `python -m pyright .`
- `python tools/smoke_refactor.py`
- `python tools/benchmark_performance.py`
- `python -m py_compile "사내 규정검색기 v9.spec"`
- `python -m unittest discover -s tests -v`
- `python -m pytest -q`
- tracked text files should remain `UTF-8` without BOM
- Windows PowerShell/Python mojibake can be a display issue rather than committed file corruption

<!-- SPECKIT-AGENT-GUIDE:START -->

## Spec Kit / Spec-Driven Development (AI 에이전트 필독)

> 이 블록은 GitHub Spec Kit 활성화 및 기능 명세 작업 결과를 AI 에이전트가 바로 쓰도록 정리한 안내입니다.
> 수정 시 마커 주석을 유지하세요. 스크립트/후속 세션이 이 구간을 갱신합니다.

### 이 저장소 상태

- **프로젝트**: `Internal-Regulations-Finder`
- **Spec Kit 초기화**: `.specify/ 있음`
- **에이전트 스킬**: Grok=True, Claude=True, Codex/Agy(.agents)=True
- **활성 기능**: 아직 `specs/` 기능 명세 없음 — `.specify/` 만 준비된 상태

### 에이전트가 먼저 읽을 파일

1. `.specify/` 및 `.grok/skills` / `.claude/skills` / `.agents/skills` 의 `speckit-*`
2. 기능 작업 시작 시 `/speckit-specify` 로 `specs/00N-...` 생성

### 권장 워크플로 (스킬 / 슬래시 커맨드)

| 단계 | 커맨드 (Grok/Claude 등) | 산출 |
|------|-------------------------|------|
| 원칙 | `/speckit-constitution` | `.specify/memory/constitution.md` |
| 명세 | `/speckit-specify` | `specs/<id>/spec.md` |
| 계획 | `/speckit-plan` | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` |
| 작업 | `/speckit-tasks` | `tasks.md` |
| 구현 | `/speckit-implement` | 코드 (tasks 순서) |
| 갭점검 | `/speckit-converge` | `tasks.md` 에 Phase Convergence **append-only** |

- Codex skills 모드: `$speckit-specify` 형태일 수 있음
- 스킬 파일: `.grok/skills/speckit-*/SKILL.md`, `.claude/skills/speckit-*/SKILL.md`

### 작업 규칙 (에이전트)

1. **새 기능/큰 변경 전** 활성 `spec.md`·`tasks.md` 를 읽고, 없으면 specify→plan→tasks 순으로 만든다.
2. **구현은 tasks.md 체크리스트**를 따른다. 완료 시 `- [ ]` → `- [x]`.
3. **`/speckit-converge` 는 tasks.md 를 rewrite 하지 않는다** — 잔여 갭만 하단 Phase 로 append.
4. brownfield 프로젝트는 상당 기능이 이미 있을 수 있다. 중복 구현 전에 코드·`[x]` 태스크를 확인한다.
5. 웹/데스크톱 패리티 등 **out-of-scope Assumptions** 는 새 feature 로 분리하는 것을 선호한다.
6. 기본 integration 은 **grok** 이며, 동일 레포에 claude / codex / agy 스킬도 multi-install 되어 있을 수 있다.

### 관련 링크

- Spec Kit: https://github.com/github/spec-kit
- 로컬 CLI: `specify` (uv tool, 버전은 `specify version`)

<!-- SPECKIT-AGENT-GUIDE:END -->
