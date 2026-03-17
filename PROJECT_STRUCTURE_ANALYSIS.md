# Internal Regulations Finder 구조 분석 및 반영 현황

## 1) 분석 기준 문서

- `README.md`
- `claude.md`
- `gemini.md`
- `docs/refactor_mapping.md`
- `docs/refactor_checklist.md`

---

## 2) 현재 구조 요약

### 핵심 모듈

- `regfinder/main_window.py`: 메인 이벤트 오케스트레이션
- `regfinder/main_window_ui_mixin.py`: UI 빌더 메서드
- `regfinder/main_window_mixins.py`: 설정/진단/북마크 보조 로직
- `regfinder/qa_system.py`: 인덱싱/검색 코어
- `regfinder/qa_system_mixins.py`: 진단/상태 API
- `regfinder/persistence.py`: 설정 스키마 + JSON 저장소
- `regfinder/worker_registry.py`: 작업별 워커 관리

### 테스트

- `tests/test_bm25_state.py`
- `tests/test_document_extractor_hwp.py`
- `tests/test_document_extractor_pdf.py`
- `tests/test_embedding_runtime_validation.py`
- `tests/test_file_utils.py`
- `tests/test_model_download_thread.py`
- `tests/test_persistence.py`
- `tests/test_repo_text_encoding.py`
- `tests/test_qa_state_reset.py`
- `tests/test_runtime_logging.py`
- `tests/test_runtime_paths.py`
- `tests/test_search_features.py`
- `tests/test_ui_style.py`
- `tests/test_worker_registry.py`

### 저장소 품질 자산

- `pyrightconfig.json`: `pythonVersion=3.14`, `typeCheckingMode=standard`
- `.editorconfig`: UTF-8(no BOM), LF, final newline 기본 정책
- `.gitattributes`: 추적 텍스트 파일 line ending 정규화
- `.vscode/settings.json`: VSCode workspace UTF-8/Pylance/Python 터미널 출력 정책 고정
- `.gitignore`: 포터블 실행 시 생성될 로컬 상태/내보내기 산출물 분리

---

## 3) 리스크 항목 처리 결과

### 기존 리스크

1. `main_window.py`, `qa_system.py` 비대화  
2. UI가 서비스 내부 메서드 직접 접근  
3. 단일 `self.worker` 구조  
4. 기능 단위 테스트 부족  
5. `file_utils.py`의 `os` 누락

### 처리 상태

1. **완료(부분 개선)**  
   - `main_window.py`: 단일 대형 파일에서 믹스인 분리 후 후속 UX/type refinements까지 반영  
   - `qa_system.py`: 진단/상태 API 분리
2. **완료**  
   - UI는 `RegulationQASystem` public API 사용
3. **완료**  
   - `WorkerRegistry` 도입
4. **완료(기초 세트)**  
   - 핵심 회귀 테스트 세트 확장
5. **완료**  
   - `file_utils.py`에 `import os` 반영

---

## 4) 기능 반영 현황

### 1순위

1. 검색 필터(확장자/경로/파일명): **완료**
2. 검색 정렬(점수/파일명/최근수정): **완료**
3. 북마크 및 내보내기: **완료**
4. 최근 폴더 다중 관리: **완료**

### 2순위

1. 인덱스 상태 진단 화면: **완료**
2. 오류 코드별 가이드 메시지: **완료**
3. 검색 로그 요약: **완료**
4. 설정 스키마 버전 관리: **완료** (`CONFIG_SCHEMA_VERSION=2`)

---

## 5) .spec 점검 결과

`사내 규정검색기 v9 PyQt6.spec`에 신규 모듈 hiddenimports 반영 필요가 있었고 반영 완료:

- `regfinder.persistence`
- `regfinder.worker_registry`
- `regfinder.main_window_ui_mixin`
- `regfinder.main_window_mixins`
- `regfinder.qa_system_mixins`

추가 정렬 사항:

- 개발 전용 품질 도구(`pytest`, `pyright`)는 번들 제외
- `pyrightconfig.json`, `.editorconfig`, `.gitattributes`는 개발 자산이며 번들 대상 아님
- offline embeddings 런타임 유지를 위해 `sentence-transformers`, `scikit-learn`, `pillow` 메타데이터 번들 유지
- frozen(onefile) 다운로드 경로는 in-process 실행으로 유지

---

## 5-1) 최근 안정화 반영

1. 로깅 `op_id` 충돌 제거  
   - `LoggerAdapter(extra={"op_id": ...})`와 formatter 기본값 충돌 없이 동작하도록 정리
2. 오프라인 모델 다운로드 초기화 예외 처리 보강  
   - 다이얼로그 초기화 실패 시 강제 종료 대신 오류 표시
3. packaged EXE 임베딩 의존성 사전검증 추가  
   - `Pillow` → `scikit-learn` → `sentence_transformers` 순으로 import 검증
4. 빈 상태 UI 스타일 회귀 수정  
   - 전역 `QWidget` 배경 적용을 화면 컨테이너로 한정
5. 모델 선택 UX 개선  
   - 모델 로드 완료 직후 검색 입력 활성화
   - 다운로드 완료 모델 우선 정렬/선택 및 Hugging Face 캐시 구조 기반 상태 판별
6. Pylance/UTF-8 회귀 방지
   - `ModelDownloadState` 타입 계약 도입으로 모델 다운로드 상태 접근 강타입화
   - `tests/test_repo_text_encoding.py`로 추적 텍스트 파일 UTF-8 디코딩 및 replacement char 회귀 검증

---

## 6) 문서/정합성 기준

- `README.md`, `claude.md`, `gemini.md`, `docs/*.md`는 현재 코드 구조와 검증 명령을 기준으로 유지
- 기본 검증 게이트는 `pyright .`, `python tools/smoke_refactor.py`, `python -m pytest -q`
- 추적 텍스트 파일은 `UTF-8(no BOM)` 기준 유지
- Windows PowerShell/Python 출력의 표시 깨짐은 실제 저장소 인코딩 손상과 구분해서 확인

---

## 7) 권장 후속 작업

1. E2E UI 테스트(Playwright/PyQt 자동화) 추가
2. 검색/인덱싱 성능 벤치마크 스크립트 추가
3. `main_window.py`의 나머지 이벤트 핸들러도 단계 분리 검토
