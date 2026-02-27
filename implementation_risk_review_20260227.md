# 기능 구현 점검 리포트 (2026-02-27)

## 1) 점검 범위
- 기준 문서: `README.md`, `claude.md`
- 핵심 코드: `regfinder/*.py`, 엔트리/스펙, `tools/smoke_refactor.py`
- 실행 검증: 스모크 체크 + 일부 런타임 재현

## 2) 총평
- 즉시 수정 필요: 1건
- 높은 우선순위: 2건
- 중간 우선순위: 3건
- 낮은 우선순위: 2건

핵심적으로는 `파일 열기/메타 조회 런타임 오류`, `모델 재로드 시 내부 상태 불일치`, `종료 시 스레드 정리 미흡`이 실제 장애로 이어질 가능성이 큽니다.

## 3) 상세 이슈

### [CRITICAL] FI-001 `FileUtils`에서 `os` 미 import로 주요 기능 런타임 실패
- 위치:
  - `regfinder/file_utils.py:4-6`
  - `regfinder/file_utils.py:42`
  - `regfinder/file_utils.py:52`
- 문제:
  - `get_metadata()`와 `open_file()`가 `os`를 사용하지만 모듈 import가 없어 `NameError` 발생.
  - 파일 목록 메타 수집, 파일 열기 기능이 런타임에서 실패.
- 재현:
  - `python -`로 `FileUtils.get_metadata(__file__)` 호출 시 `NameError: name 'os' is not defined`
  - `FileUtils.open_file('.')` 호출 시 로그에 `파일 열기 실패: name 'os' is not defined`
- 영향:
  - 문서 처리 전 메타/크기 계산 신뢰성 저하
  - UI의 파일 열기 액션 무력화
- 권장 조치:
  1. `import os` 추가
  2. 최소 단위 회귀 테스트 추가 (`get_metadata`, `open_file` 분기)

### [HIGH] MW-001 모델 즉시 변경 시 내부 상태 초기화 불완전
- 위치:
  - `regfinder/main_window.py:460-482`
  - `regfinder/main_window.py:431-443`
  - `regfinder/qa_system.py:584-585`
- 문제:
  - `_reload_model()`에서 `vector_store/documents/doc_meta/bm25`만 초기화하고 `doc_ids`, `embedding_model`, `model_id`는 유지됨.
  - `_on_model_loaded()` 실패 분기에서 폴더 버튼/최근 버튼을 비활성화하지 않음.
- 영향:
  - 모델 재로드 실패 시, 사용자 선택 모델과 실제 사용 모델이 불일치할 수 있음(구 모델 잔존 가능).
  - `doc_ids` 잔존 시 BM25 결합 단계에서 문서-메타 매핑 불일치 위험.
- 권장 조치:
  1. 모델 변경 직전 `doc_ids`, `embedding_model`, `model_id`, `current_folder`까지 원자적으로 초기화
  2. 모델 로드 실패 시 폴더 로드 관련 버튼 상태를 명시적으로 잠금
  3. 모델 변경 플로우 전용 회귀 테스트(성공/실패 케이스) 추가

### [HIGH] MW-002 앱 종료 시 실행 중 워커 스레드 정리 누락
- 위치:
  - `regfinder/main_window.py:1109-1112`
  - `regfinder/workers.py:23-27`
- 문제:
  - `closeEvent()`에서 `self.qa.cleanup()`만 호출하고 실행 중인 `QThread` cancel/wait 처리 없음.
  - 문서 처리/다운로드 중 종료 시 캐시/상태 정합성 문제 또는 종료 불안정 가능.
- 영향:
  - 간헐적인 종료 이슈, 리소스 누수, 불완전 캐시 저장 가능성
- 권장 조치:
  1. `closeEvent()`에서 활성 워커(`self.worker`, `self.download_worker`)에 `cancel()` 호출
  2. `wait(timeout)` 후 안전 종료
  3. 종료 중 UI 재진입 방지 플래그 추가

### [MEDIUM] RT-001 README의 "실행 폴더 저장" 정책과 실제 경로 산정 불일치
- 위치:
  - 문서: `README.md:137-139`
  - 코드: `regfinder/runtime.py:64-69`, `regfinder/runtime.py:91-93`
- 문제:
  - 비-frozen 실행 시 `get_app_directory()`가 엔트리 실행 위치가 아니라 `regfinder` 패키지 경로를 반환.
  - 문서의 "우선 실행 폴더" 설명과 동작이 다르게 보일 수 있음.
- 재현:
  - 출력 예시: `app_dir=...\Internal-Regulations-Finder\regfinder`
- 영향:
  - 운영/배포 시 설정/로그/모델 위치 혼선
- 권장 조치:
  1. 문서 기준을 코드에 맞추거나, 코드 기준을 문서에 맞춤(둘 중 하나로 정합성 확보)
  2. 설정 탭에 실제 data/models/logs 경로를 더 명확히 표시

### [MEDIUM] QA-001 "캐시 삭제"가 메모리 인덱스는 유지
- 위치:
  - `regfinder/qa_system.py:735-738`
  - `regfinder/main_window.py:971-977`
- 문제:
  - 디스크 캐시만 삭제하고 메모리의 `vector_store/documents/doc_meta/doc_ids`는 유지.
- 영향:
  - 사용자 입장에서는 캐시 삭제 후에도 검색이 계속 동작해 기대와 다를 수 있음.
- 권장 조치:
  1. 버튼 라벨을 "디스크 캐시 삭제"로 명확화 또는
  2. 캐시 삭제 시 메모리 인덱스도 함께 초기화(검색 비활성화)

### [MEDIUM] DL-001 모델 다운로드 취소 응답성 부족
- 위치:
  - `regfinder/workers.py:88-103`
- 문제:
  - 취소 체크가 모델 단위 루프 시작 시점에만 수행됨.
  - 단일 모델 다운로드가 길면 취소가 즉시 반영되지 않음.
- 영향:
  - 대용량 다운로드 체감 UX 저하, 종료 지연
- 권장 조치:
  1. 다운로드를 더 작은 단계로 쪼개거나
  2. 취소 가능한 다운로드 경로(라이브러리/프로세스 레벨) 도입

### [LOW] UX-001 최소 검색어 길이 사전 검증 누락
- 위치:
  - `regfinder/main_window.py:627-633`
  - `regfinder/qa_system.py:503-504`
- 문제:
  - UI에서 빈 문자열만 막고 1글자 질의는 스레드 실행 후 오류 표시.
- 영향:
  - 불필요한 스레드 생성 + 에러 다이얼로그 노출
- 권장 조치:
  1. UI단에서 `len(query) < 2` 즉시 안내

### [LOW] QA-002 문서가 비어질 때 BM25 상태 초기화 누락 가능성
- 위치:
  - `regfinder/qa_system.py:452-455`
- 문제:
  - `_build_bm25()`는 `self.documents`가 있을 때만 재생성하며, 비어 있을 때 명시적으로 `self.bm25=None` 처리하지 않음.
- 영향:
  - 경계 케이스에서 내부 상태 추적이 어려워질 수 있음.
- 권장 조치:
  1. 문서 0건이면 `self.bm25 = None`로 상태 명확화

## 4) 추가 권장 구현 항목

### A. 회귀 테스트 강화 (우선)
- `tests/test_file_utils.py`: `get_metadata/open_file` 기본 동작
- `tests/test_model_reload_state.py`: 모델 변경 성공/실패 시 내부 상태 검증
- `tests/test_shutdown_threads.py`: 처리 중 종료 시 cancel/wait 보장
- `tests/test_cache_clear_semantics.py`: 캐시 삭제 후 검색 가능 여부 정책 고정

### B. 사용자 혼선 방지 UX
- 설정 탭에 "현재 실제 데이터 경로"를 더 크게 노출
- 캐시 삭제 버튼 의미를 디스크/메모리로 분리
- 검색어 길이, 모델 로드 상태를 검색 버튼 enable 조건에 통합

### C. 알려진 제한 고도화(README 연계)
- 이미지 PDF용 OCR 옵션
- 암호화 PDF 비밀번호 입력 UI
- HWP 다중 섹션/변형 포맷 대응성 개선

## 5) 점검 중 실행한 검증
- `python tools/smoke_refactor.py` 통과
  - `py_compile/import/sanity` OK
- 수동 재현
  - `FileUtils.get_metadata()` NameError 재현
  - `get_app_directory()` 경로가 `regfinder`로 반환됨 확인

## 6) 개선 적용 체크 (2026-02-27)
- [x] FI-001 `file_utils.py`의 `os` 미 import 수정
- [x] MW-001 모델 재로드 상태 초기화(`reset_runtime_state`) 및 실패 시 UI 잠금 강화
- [x] MW-002 종료 시 워커 cancel/wait/다이얼로그 정리 추가
- [x] RT-001 `get_app_directory()`를 `sys.argv[0]` 기반으로 수정
- [x] QA-001 캐시 삭제를 디스크+메모리 동시 초기화로 변경
- [x] DL-001 모델 다운로드 취소 응답성(300ms poll + subprocess terminate) 개선
- [x] UX-001 1글자 검색어 UI 사전 차단 추가
- [x] QA-002 문서 0건 시 BM25 상태를 `None`으로 명확화
- [x] 암호 PDF 즉시 비밀번호 입력 + 세션 재사용 플로우 추가
- [x] OCR 인터페이스(`BaseOCREngine`/`NoOpOCREngine`) 추가
- [x] HWP 다중 섹션(`BodyText/Section*`) 우선 추출 + 원인 메시지 보강
- [x] pytest 테스트 체계 도입(`pytest.ini` + `tests/` 6개 파일)

## 7) 문서/스펙 정합성 반영 (2026-02-27)
- [x] `README.md` 기능/검증/제한사항을 코드 동작과 동기화
- [x] `claude.md`, `gemini.md`에 최신 추출/캐시/다운로드/경로 정책 반영
- [x] `docs/refactor_checklist.md`에 신규 검증 항목(암호 PDF, pytest, 종료 정리) 반영
- [x] `docs/refactor_mapping.md`에 post-refactor 정렬 항목 추가
- [x] `사내 규정검색기 v9 PyQt6.spec` 주석에 frozen 다운로드 폴백 동작 명시

