# Refactor Mapping (v9.3)

## Goal
단일 파일 `사내 규정검색기 v9 PyQt6.py`를 `regfinder` 패키지로 분할하되, 실행/배포 인터페이스를 유지한다.

## File Mapping

| Old location | New location | Moved symbols |
|---|---|---|
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/app_types.py` | `AppConfig`, `TaskStatus`, `FileStatus`, `TaskResult`, `FileInfo` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/runtime.py` | `_import_module`, `_import_attr`, `_log_record_factory`, `new_op_id`, `OpLoggerAdapter`, `get_op_logger`, data/config path helpers, `setup_logger`, `logger` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/file_utils.py` | `FileUtils` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/bm25.py` | `BM25Light` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/document_extractor.py` | `DocumentExtractor` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/qa_system.py` | `RegulationQASystem` (all methods) |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/workers.py` | `BaseWorkerThread`, `ModelLoaderThread`, `ModelDownloadThread`, `DocumentProcessorThread`, `SearchThread` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/ui_style.py` | `DARK_STYLE` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/ui_components.py` | `SearchHistory`, `ResultCard`, `EmptyStateWidget`, `ProgressDialog`, `DebugDetailsDialog` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/main_window.py` | `MainWindow` (all methods) |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/app_main.py` | `main` |
| `사내 규정검색기 v9 PyQt6.py` | `사내 규정검색기 v9 PyQt6.py` | compatibility wrapper + symbol re-export |

## Compatibility Notes

- 실행 명령 유지: `python "사내 규정검색기 v9 PyQt6.py"`
- PyInstaller 진입 파일 유지: `사내 규정검색기 v9 PyQt6.spec`의 `Analysis(['사내 규정검색기 v9 PyQt6.py'])` 유지
- 래퍼 파일에서 `AppConfig`, `RegulationQASystem`, `MainWindow`, `main` 포함 주요 심볼 re-export
- `spec`에서 `pathex`는 프로젝트 루트를 포함하고, `regfinder.*` hiddenimports를 명시하여 onefile 빌드 안정성 보강

## Minor Safe Fix Included

- `MainWindow._update_internal_state_display`의 `last_op` 키 참조를 실제 저장 키와 정렬
  - `type/status` 중심 참조에서 `kind/success` 우선 참조로 보정

## Post-Refactor Functional Alignment (2026-02-27)

- `runtime.get_app_directory`:
  - non-frozen에서 `sys.argv[0]` 기준 실행 경로 사용, 실패 시 `os.getcwd()` 폴백
- `qa_system`:
  - `reset_runtime_state(reset_model=False)` 추가
  - `process_documents(..., pdf_passwords, ocr_options)` 확장
  - `clear_cache(reset_memory=True)`로 디스크+메모리 동시 초기화
  - 문서 0건 시 BM25를 `None`으로 명시
- `document_extractor`:
  - `check_pdf_encrypted` 추가
  - PDF 추출 시 비밀번호/OCREngine 훅 지원
  - `BaseOCREngine`, `NoOpOCREngine` 추가
  - HWP `BodyText/Section*` 다중 섹션 + raw-deflate 시도
- `workers`:
  - `DocumentProcessorThread`가 `pdf_passwords`, `ocr_options` 전달
  - 모델 다운로드는 script 모드 subprocess(300ms poll 취소), frozen 모드 in-process 폴백
- `main_window`:
  - 암호 PDF 사전 점검/비밀번호 입력/세션 재사용
  - 캐시 삭제 시 검색 UI 잠금 및 재로드 유도 메시지
  - 종료 시 워커 cancel/wait 및 progress dialog 안전 종료
