# Refactor Mapping (v9.3)

## Goal

단일 파일 구조를 `regfinder` 패키지로 분할하고, 이후 유지보수성과 운영 안정성을 높이는 2차 분리까지 반영한다.

---

## Phase 1: Single-file → Package

| Old | New |
|---|---|
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/app_types.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/runtime.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/file_utils.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/bm25.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/document_extractor.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/qa_system.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/workers.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/ui_style.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/ui_components.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/main_window.py` |
| `사내 규정검색기 v9 PyQt6.py` | `regfinder/app_main.py` |

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

## Compatibility Notes

- 실행 엔트리 유지: `python "사내 규정검색기 v9 PyQt6.py"`
- PyInstaller 진입 유지: `사내 규정검색기 v9 PyQt6.spec`
- spec hiddenimports에 신규 internal 모듈 추가 반영
- frozen(onefile) 모델 다운로드는 subprocess 대신 in-process 경로로 폴백
- spec은 offline embeddings를 위해 `sentence-transformers` / `scikit-learn` / `pillow` 메타데이터를 포함
- 정적 분석 기준은 `pyrightconfig.json`으로 저장소 루트에 고정
- 텍스트 인코딩/줄바꿈 정책은 `.editorconfig` + `.gitattributes`로 고정
- VSCode workspace 설정은 `.vscode/settings.json`으로 UTF-8/Pylance 범위를 고정
- 모델 다운로드 상태 UI는 `ModelDownloadState` 타입 계약으로 강타입화

---

## Repository Hygiene

- `pyright .` 기준 오류 0건 유지
- 추적 텍스트 파일은 `UTF-8(no BOM)` 유지
- `tests/test_repo_text_encoding.py`로 UTF-8 디코딩/replacement char 회귀 검증 유지
- Windows PowerShell/Python 출력 모지바케는 실제 저장소 파일 손상과 분리해 판단
- 런타임 로컬 상태 파일과 결과 내보내기 산출물은 `.gitignore`로 분리 관리
