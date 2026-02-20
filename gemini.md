# 🤖 Gemini AI Guidelines: 사내 규정 검색기 v9.3 (Modular Deep Dive)

이 문서는 **모듈 분할 리팩토링 이후 구조**를 기준으로 프로젝트 동작을 이해하고 유지보수하기 위한 가이드입니다.

---

## 🏗️ 아키텍처 개요

### 1) 엔트리와 호환성
- 사용자 실행: `python "사내 규정검색기 v9 PyQt6.py"`
- 해당 파일은 호환 래퍼이며 내부적으로 `regfinder.app_main.main()` 호출

### 2) 모듈 책임 분리
- `regfinder/app_types.py`: 공용 타입/설정
- `regfinder/runtime.py`: 로깅, 경로 정책, 동적 import 유틸
- `regfinder/qa_system.py`: 인덱싱/검색/캐시/진단 핵심 로직
- `regfinder/main_window.py`: UI 이벤트/화면 상태 제어
- `regfinder/workers.py`: 모델 로드/문서 처리/검색/다운로드 워커
- `regfinder/ui_components.py`, `regfinder/ui_style.py`: UI 구성요소/스타일

---

## ⚙️ 주요 설정 (`AppConfig`)

- `CHUNK_SIZE = 800`
- `CHUNK_OVERLAP = 80`
- `VECTOR_WEIGHT = 0.7`
- `BM25_WEIGHT = 0.3`
- `SUPPORTED_EXTENSIONS = ('.txt', '.docx', '.pdf', '.hwp')`

---

## 🔍 핵심 로직 요약

### RegulationQASystem
- 증분 인덱싱: 파일 `size`/`mtime` 비교
- 캐시 루트: `%TEMP%/reg_qa_v90`
- 캐시 스키마 검증 실패 시 안전 삭제 후 재생성
- 하이브리드 점수: 벡터 + BM25 정규화 결합

### BM25Light
- 한국어/영문 혼합 토큰 처리
- 조사 제거(간이) 및 길이 필터
- `avgdl` 0 분모 방어

---

## 🌐 오프라인/진단

- 설정 탭의 `📥 오프라인 모델 다운로드`에서 선택 다운로드 지원
- 타임아웃: `HF_HUB_DOWNLOAD_TIMEOUT = 300`
- 모델/설정/로그 저장 위치는 `get_data_directory()` 정책(포터블 우선 + 사용자 폴더 폴백)
- `🧰 진단 내보내기`: 환경/설정/로그/캐시 요약 zip 생성

---

## 🧵 스레드 안전 규칙

1. `run()` 내부에서 UI 직접 갱신 금지
2. 시그널로만 UI 스레드에 전달
3. 취소는 `cancel()` + `is_canceled()`로 처리
4. 완료 후 `deleteLater()` 및 참조 해제(`worker = None`)

---

## 🛠️ 유지보수 검증 루틴

### 심볼 누락 검증

```bash
python tools/symbol_inventory.py --paths regfinder "사내 규정검색기 v9 PyQt6.py" --out artifacts/symbols_after.json --compare-before artifacts/symbols_before.json --compare-after artifacts/symbols_after.json
```

### 스모크 검증

```bash
python tools/smoke_refactor.py
```

검증 항목:
- 정적 컴파일
- 모듈 import
- 심볼 전후 diff
- 핵심 객체 생성 sanity check

---

## 📦 빌드 기준

- 명령: `pyinstaller "사내 규정검색기 v9 PyQt6.spec"`
- 출력: `dist/사내 규정검색기 v9.3_onefile.exe`
- spec에서 `regfinder.*` hidden import와 `pathex`(프로젝트 루트) 반영
