# Refactor Mapping (v9.3)

## Goal

단일 파일 구조를 `regfinder` 패키지로 분할하고, 이후 유지보수성과 운영 안정성을 높이는 2차 분리, 검색 품질 리팩토링, 기능별 하위 패키지 리팩토링까지 반영한다.

---

## Phase 1: Single-file → Package

| Old | New |
|---|---|
| `사내 규정검색기 v9.py` | `regfinder/app_types.py` |
| `사내 규정검색기 v9.py` | `regfinder/runtime.py` |
| `사내 규정검색기 v9.py` | `regfinder/file_utils.py` |
| `사내 규정검색기 v9.py` | `regfinder/bm25.py` |
| `사내 규정검색기 v9.py` | `regfinder/document_extractor.py` |
| `사내 규정검색기 v9.py` | `regfinder/qa_system.py` |
| `사내 규정검색기 v9.py` | `regfinder/workers.py` |
| `사내 규정검색기 v9.py` | `regfinder/ui_style.py` |
| `사내 규정검색기 v9.py` | `regfinder/ui_components.py` |
| `사내 규정검색기 v9.py` | `regfinder/main_window.py` |
| `사내 규정검색기 v9.py` | `regfinder/app_main.py` |

---

## Phase 2: Maintainability / Runtime Hardening

| Source | Extracted/Added | Purpose |
|---|---|---|
| `regfinder/main_window.py` | `regfinder/main_window_ui_mixin.py` | UI 빌더 메서드 분리 |
| `regfinder/main_window.py` | `regfinder/main_window_mixins.py` | 설정/진단/북마크 로직 분리 |
| `regfinder/qa_system.py` | `regfinder/qa_system_mixins.py` | 진단/상태 API 분리 |
| 신규 | `regfinder/persistence.py` | 설정 스키마/JSON 저장소 통합 |
| 신규 | `regfinder/worker_registry.py` | 단일 워커 슬롯 제거 |

---

## Phase 3: Performance Refactor / Cache Split

| Source | Extracted/Added | Purpose |
|---|---|---|
| `regfinder/qa_system.py` | `regfinder/text_cache.py` | SQLite 기반 텍스트 캐시 |
| `regfinder/main_window.py` | `regfinder/model_inventory.py` | 모델 다운로드 상태/용량 캐시 |
| `regfinder/file_utils.py` | `DiscoveredFile` 흐름 | `os.scandir` 기반 파일 discovery + 메타 재사용 |
| `regfinder/bm25.py` | `BM25Index` | posting 기반 후보 축소 검색 |
| 신규 | `tools/benchmark_performance.py` | startup/discover/index/search/model-switch 벤치마크 |

---

## Phase 4: Search Quality / UX Hardening

| Source | Extracted/Added | Purpose |
|---|---|---|
| 신규 | `regfinder/search/text.py` | 공용 검색 정규화 / 토큰 확장 / 필터 매칭 |
| `regfinder/qa_system.py` | file-level result aggregation | `match_count`, `snippet_chunk_idx`, 대표 청크 선정 |
| `regfinder/qa_system.py` | degraded search mode handling | `hybrid` / `vector_only` / `bm25_only` 명시 |
| `regfinder/qa_system.py` | modified-file cache invalidation | 재추출 실패 파일의 stale text/chunk 제거 |
| `regfinder/ui_components.py` | normalized highlight spans | 조사 제거/무공백 질의와 같은 규칙으로 하이라이트 |
| `regfinder/main_window.py` | search mode + memory warning surface | UI 상태/경고/내부 진단 표시 |
| `regfinder/main_window.py` | encrypted PDF preflight + cache reset sync | 세션 비밀번호 수집/재사용, 캐시 삭제 후 UI 동기화 |
| `regfinder/main_window.py` / `regfinder/main_window_mixins.py` | csv-safe exports | 검색 결과/북마크 CSV escaping 일원화 |
| `regfinder/ui_components.py` | ranking score / evidence labels | `랭킹 점수`, `근거 청크 n개` UI 표기 |

---

## Phase 5: UI/UX Consistency / Typing Hygiene

| Source | Extracted/Added | Purpose |
|---|---|---|
| `regfinder/main_window.py` | busy-state orchestration | model/docs/download는 strong busy, search는 inline busy로 분리 |
| `regfinder/ui_components.py` | `SearchProgressCard`, `ResultDetailDialog` | 검색 진행 표시/취소, 결과 상세 탐색 |
| `regfinder/ui_components.py` | expanded `SearchHistory` schema | `q + filters + sort_by + k + hybrid` 저장 |
| `regfinder/main_window.py` / `regfinder/main_window_mixins.py` | numeric table items | 파일/북마크 숫자 정렬 정합화 |
| `regfinder/runtime.py` | writable logger fallback | sandbox/test/import 환경에서 로그 초기화 실패 방지 |
| `regfinder/text_cache.py` | file fingerprint metadata | same-size modified file stale cache 탐지 강화 |
| 저장소 루트 | `pyrightconfig.json`, `.vscode/settings.json`, `.gitignore` | Pyright/Pylance/로컬 temp/log 정합성 유지 |

---

## Compatibility Notes

- 실행 엔트리 유지: `python "사내 규정검색기 v9.py"`
- PyInstaller 진입 유지: `사내 규정검색기 v9.spec`
- 기존 public import 유지: `regfinder.qa_system`, `regfinder.main_window`, `regfinder.workers`, `regfinder.search_text` 등은 compatibility wrapper로 유지
- wrapper는 실제 구현 모듈로 alias되어 기존 테스트 monkeypatch 경로도 동일하게 동작
- spec hiddenimports에 신규 internal 모듈 추가 반영
- spec hiddenimports에 compatibility modules와 feature package modules를 함께 반영
- spec hiddenimports에 `regfinder.storage.text_cache`, `regfinder.storage.model_inventory`, `regfinder.search.text`, `charset_normalizer`, 선택형 OCR 모듈(`pytesseract`, `fitz`) 추가 반영
- frozen(onefile) 모델 다운로드는 subprocess 대신 in-process 경로로 폴백
- spec은 offline embeddings를 위해 `sentence-transformers` / `scikit-learn` / `pillow` 메타데이터를 포함
- lazy 인코딩 fallback을 위해 `charset_normalizer`는 spec에서 제외 금지
- 선택형 Tesseract OCR은 Python 모듈 import만으로 충분하지 않고 외부 Tesseract 실행 파일/언어 데이터가 필요
- 정적 분석 기준은 `pyrightconfig.json`으로 저장소 루트에 고정
- `pyrightconfig.json` / `.vscode/settings.json`은 optional dependency missing-import 노이즈를 낮추되 내부 타입 오류는 유지
- 텍스트 인코딩/줄바꿈 정책은 `.editorconfig` + `.gitattributes`로 고정
- VSCode workspace 설정은 `.vscode/settings.json`으로 UTF-8/Pylance 범위를 고정
- 모델 다운로드 상태 UI는 `ModelDownloadState` 타입 계약으로 강타입화
- 캐시 스키마는 `CACHE_SCHEMA_VERSION=4`, 설정 스키마는 `CONFIG_SCHEMA_VERSION=4`

---

## Phase 6: Implementation Risk Hardening (2026-04-16)

| Source | Extracted/Added | Purpose |
|---|---|---|
| `regfinder/model_inventory.py` | deadlock-safe `snapshot()` | 빈 인벤토리 첫 조회 시 lock 재진입 교착 방지 |
| `regfinder/file_utils.py` | `skipped_paths` discovery flow | 권한 없는 하위 폴더를 전체 실패 대신 skip |
| `regfinder/main_window.py` | delayed folder label commit / skip notice | 폴더 로드 성공 전 UI 상태 오염 방지 및 제외 경로 공지 |
| `regfinder/main_window_ui_mixin.py` / `main_window_mixins.py` | OCR controls + persisted config | OCR 운영 옵션을 UI와 설정에 연결 |
| `regfinder/document_extractor.py` | mixed PDF OCR append | 일부 페이지만 비어 있는 PDF에 OCR 텍스트 병합 |
| `regfinder/qa_system.py` | state capture/restore | folder load cancel/fail 시 이전 인덱스 상태 복원 |
| `regfinder/qa_system.py` | model-less BM25 processing | embedding model 없이도 초기 BM25 인덱싱 허용 |
| `regfinder/ui_components.py` | exact-context history dedup | query만이 아닌 전체 검색 조건 기준 dedup |
| `regfinder/worker_registry.py` / `main_window.py` | worker wait on shutdown | cancel 후 registry/runtime cleanup 순서 안정화 |

---

## Phase 7: Functional Implementation Hardening (2026-04-28)

| Source | Extracted/Added | Purpose |
|---|---|---|
| `regfinder/storage/persistence.py` | config schema v4 coercion | 잘못된 설정 타입/값을 안전한 기본값으로 복구 |
| `regfinder/search/diagnostics.py` | diagnostics privacy mode | 진단 ZIP에서 원문 텍스트 캐시를 기본 제외하고 명시 선택 시만 포함 |
| `regfinder/search/qa_system.py` | `DOCS_CANCELED` / state restore | 벡터 인덱싱 취소와 실패 분리, 이전 인덱스 상태 복구 |
| `regfinder/search/qa_system.py` | BM25-only vector promotion | 모델 로드 후 기존 BM25-only 인덱스를 하이브리드 모드로 승격 시도 |
| `regfinder/search/qa_system.py` | filtered vector fetch cap | 필터 검색 fetch 상한과 `vector_limit_reached` 진단 |
| `regfinder/search/qa_system.py` | BM25 distinct-file expansion | 특정 파일 청크 독점 시 파일 단위 결과를 더 채움 |
| `regfinder/documents/extractor.py` | HWPX ZIP/XML extractor | `.hwpx` 본문 추출 지원 |
| `regfinder/documents/extractor.py` | PDF page segments | chunk/result/detail/export에 page metadata 전달 |
| `regfinder/documents/extractor.py` | `TesseractOCREngine` | 선택형 OCR lazy import 및 명확한 fallback 안내 |
| `regfinder/ui/main_window.py` / `regfinder/ui/components.py` | diagnostics checkbox / page labels / cancel close | 진단 원문 포함 UI, PDF page 표시, ProgressDialog 닫기 취소 |
| `regfinder/core/runtime.py` | stricter model cache check | snapshot metadata와 가중치 파일 기반 다운로드 완료 판정 |
| `regfinder/core/types.py` | HWPX/OCR/vector cap constants | 지원 확장자와 운영 상수 갱신 |

---

## Phase 8: Feature Package Refactor (2026-04-28)

| Previous implementation module | New implementation module |
|---|---|
| `regfinder/app_types.py` | `regfinder/core/types.py` |
| `regfinder/runtime.py` | `regfinder/core/runtime.py` |
| `regfinder/file_utils.py` | `regfinder/core/file_utils.py` |
| `regfinder/persistence.py` | `regfinder/storage/persistence.py` |
| `regfinder/text_cache.py` | `regfinder/storage/text_cache.py` |
| `regfinder/model_inventory.py` | `regfinder/storage/model_inventory.py` |
| `regfinder/document_extractor.py` | `regfinder/documents/extractor.py` |
| `regfinder/search_text.py` | `regfinder/search/text.py` |
| `regfinder/bm25.py` | `regfinder/search/bm25.py` |
| `regfinder/qa_system.py` | `regfinder/search/qa_system.py` |
| `regfinder/qa_system_mixins.py` | `regfinder/search/diagnostics.py` |
| `regfinder/workers.py` | `regfinder/application/workers.py` |
| `regfinder/worker_registry.py` | `regfinder/application/worker_registry.py` |
| `regfinder/app_main.py` | `regfinder/application/app_main.py` |
| `regfinder/ui_style.py` | `regfinder/ui/style.py` |
| `regfinder/ui_components.py` | `regfinder/ui/components.py` |
| `regfinder/main_window.py` | `regfinder/ui/main_window.py` |
| `regfinder/main_window_ui_mixin.py` | `regfinder/ui/window_builder.py` |
| `regfinder/main_window_mixins.py` | `regfinder/ui/window_mixins.py` |

기존 top-level `regfinder/*.py` 파일은 삭제하지 않고 compatibility wrapper로 유지한다. 이는 외부 스크립트, 테스트 monkeypatch, PyInstaller hiddenimports가 기존 경로를 계속 사용할 수 있게 하기 위한 의도적인 API 표면이다.

---

## Repository Hygiene

- `python -m pyright .` 기준 오류 0건 유지
- 추적 텍스트 파일은 `UTF-8(no BOM)` 유지
- `tests/test_repo_text_encoding.py`로 UTF-8 디코딩/replacement char 회귀 검증 유지
- Windows PowerShell/Python 출력 모지바케는 실제 저장소 파일 손상과 분리해 판단
- 런타임 로컬 상태 파일과 결과 내보내기 산출물은 `.gitignore`로 분리 관리
- `.pytest_localappdata/`, `.regfinder_logs/`는 로컬 테스트/로그 디렉터리로 커밋 대상이 아님
