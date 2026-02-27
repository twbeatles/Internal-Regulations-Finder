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

- `tests/test_file_utils.py`
- `tests/test_persistence.py`
- `tests/test_search_features.py`
- `tests/test_worker_registry.py`

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
   - `main_window.py`: `1056 -> 713` lines  
   - `qa_system.py`: 진단/상태 API 분리
2. **완료**  
   - UI는 `RegulationQASystem` public API 사용
3. **완료**  
   - `WorkerRegistry` 도입
4. **완료(기초 세트)**  
   - 단위 테스트 4파일 추가
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

---

## 6) 권장 후속 작업

1. E2E UI 테스트(Playwright/PyQt 자동화) 추가
2. 검색/인덱싱 성능 벤치마크 스크립트 추가
3. `main_window.py`의 나머지 이벤트 핸들러도 단계 분리 검토
