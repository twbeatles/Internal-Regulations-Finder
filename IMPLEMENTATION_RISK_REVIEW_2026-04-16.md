# 구현 리스크 점검 및 조치 결과 (2026-04-16)

이 문서는 2026-04-16 기준 구현 리스크 점검 결과, 실제 코드 수정 내역, 검증 상태를 함께 정리한 기록이다.

## 점검 배경

- 참조 문서: README.md, claude.md, FUNCTIONAL_REVIEW_2026-03-19.md, UI_UX_REVIEW_2026-03-25.md
- 목표: 기능은 이미 동작하더라도, 실제 운용 시 잠재적으로 문제가 될 수 있는 구현 리스크를 선제적으로 줄이는 것
- 검토 범위: 인덱싱 생명주기, 모델 비의존 초기 흐름, OCR 옵션 연결, 워커 종료 순서, 검색 히스토리 정합성, 스펙/문서 동기화

## 최종 상태 요약

- 치명적 리스크 2건: 모두 수정 완료
- 중요 리스크 4건: 모두 수정 완료
- 문서/스펙 정합성 항목: 반영 완료
- 정적 타입 검사: pyright 0 errors
- 테스트: pytest 전체 통과 기준으로 재확인

## 조치 항목

### 1. 첫 실행 시 ModelInventory.snapshot() 교착 가능성 제거

- 문제
  - 첫 실행 상태에서 인벤토리 비어 있을 때 snapshot refresh 경로가 잠길 수 있었다.
- 조치
  - 빈 inventory에서도 refresh가 안전하게 완료되도록 동기화 경로를 정리했다.
- 관련 파일
  - egfinder/model_inventory.py
  - 	ests/test_model_inventory.py

### 2. 폴더 로드 취소/실패 시 기존 인덱스 복원

- 문제
  - 새 폴더를 불러오다 취소하거나 실패하면, 이전 인덱스와 새 상태가 섞여 남을 수 있었다.
- 조치
  - 문서 처리 시작 전에 인덱스 상태를 캡처하고, 비정상 종료 시 BM25/Vector/문서 메타데이터를 복원하도록 변경했다.
- 관련 파일
  - egfinder/qa_system.py
  - 	ests/test_performance_refactor.py

### 3. 임베딩 모델 없이도 초기 폴더 스캔 및 BM25-only 인덱싱 허용

- 문제
  - 첫 실행 UX가 불필요하게 모델 로드에 묶여 있어, 텍스트 위주 검색도 바로 시작할 수 없었다.
- 조치
  - 폴더 로드, 새로고침, 검색 가능 상태를 "인덱스 존재 여부" 기준으로 정리했다.
  - 벡터 인덱스는 모델이 있을 때만 생성하고, 없으면 BM25-only 흐름으로 동작하도록 분기했다.
- 관련 파일
  - egfinder/main_window.py
  - egfinder/qa_system.py
  - 	ests/test_main_window_behaviors.py
  - 	ests/test_performance_refactor.py

### 4. 접근 거부 하위 폴더를 전체 실패 대신 skip 처리

- 문제
  - 하나의 권한 없는 하위 폴더 때문에 전체 스캔이 실패할 수 있었다.
- 조치
  - 파일 탐색 단계에서 권한 예외를 skip 목록에 누적하고, 처리 완료 후 사용자에게 skip 수를 안내하도록 수정했다.
- 관련 파일
  - egfinder/file_utils.py
  - egfinder/main_window.py
  - 	ests/test_file_utils.py

### 5. OCR 옵션의 UI/설정 저장/실제 추출 경로 연결

- 문제
  - OCR 훅은 있었지만 설정 UI와 persistence, 혼합 PDF 보강 흐름이 분리되어 있었다.
- 조치
  - ocr_enabled, ocr_mixed_pdf를 설정 저장/복원에 연결했다.
  - 혼합 PDF에서 텍스트 추출이 비어 있는 페이지에 OCR 보강을 선택적으로 적용하도록 수정했다.
- 관련 파일
  - egfinder/persistence.py
  - egfinder/main_window_mixins.py
  - egfinder/main_window_ui_mixin.py
  - egfinder/document_extractor.py
  - 	ests/test_document_extractor.py

### 6. 검색 히스토리 dedup 기준을 전체 검색 컨텍스트로 확장

- 문제
  - 같은 검색어라도 필터/정렬/검색 모드가 다르면 별도 실험으로 남아야 하는데, 기존에는 검색어 문자열만 기준으로 덮어썼다.
- 조치
  - 검색어, 필터, 정렬, 결과 수, 하이브리드 여부를 포함한 entry key로 dedup 하도록 변경했다.
- 관련 파일
  - egfinder/ui_components.py
  - 	ests/test_ui_search_display.py

### 7. 종료 시 워커 취소 후 completion 대기

- 문제
  - 종료 이벤트에서 워커가 끝나기 전에 registry/state를 먼저 정리해 race 가능성이 있었다.
- 조치
  - 종료 시 취소 요청 후 짧게 완료를 기다리고, 그 다음 정리하도록 순서를 보강했다.
- 관련 파일
  - egfinder/worker_registry.py
  - egfinder/main_window.py

## 스펙 파일 점검 결과

- 대상 파일: 사내 규정검색기 v9 PyQt6.spec
- 점검 결과
  - 이번 수정으로 추가 hiddenimports, datas, binaries는 필요하지 않았다.
  - OCR 설정 persistence와 BM25-only 초기 흐름은 기존 패키징 구성 안에서 동작한다.
  - 주석/메모는 2026-04-16 기준 상태에 맞게 갱신했다.
- 검증
  - python -m py_compile "사내 규정검색기 v9 PyQt6.spec" 통과

## 문서 정합성 반영 파일

- README.md
- claude.md
- gemini.md
- PROJECT_STRUCTURE_ANALYSIS.md
- docs/refactor_mapping.md
- docs/refactor_checklist.md
- FUNCTIONAL_REVIEW_2026-03-19.md
- UI_UX_REVIEW_2026-03-25.md

## 검증 명령

`ash
python -m py_compile "사내 규정검색기 v9 PyQt6.spec"
python -m pyright .
python -m pytest -q
`

## 검증 결과

- python -m py_compile "사내 규정검색기 v9 PyQt6.spec": 통과
- python -m pyright .: 통과
- python -m pytest -q: 통과

## 후속 메모

- 검색 진행률의 세부 단계 표시, 검색 중 필터 패널 전체 잠금, skip 경로 상세 보기 UX는 여전히 별도 개선 후보로 남겨둘 수 있다.
- 이번 조치는 기능 추가보다 런타임 안정성과 사용자 혼란 감소에 초점을 둔 유지보수성 강화 작업이다.