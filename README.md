# 📚 사내 규정 검색기 v9.3

> 로컬 AI 기반 사내 규정 문서 검색 프로그램  
> PyQt6 GUI | 하이브리드 검색(Vector + BM25) | 증분 인덱싱 | 오프라인 모델 지원

---

## ✨ 핵심 기능

- 하이브리드 검색(벡터 70% + BM25 30%)
- 검색어 하이라이트, 검색 시간 표시, 결과 TXT/CSV 내보내기
- 증분 인덱싱/캐시(변경 파일만 재처리)
- 오프라인 모델 다운로드(선택 다운로드)
- 진단 번들(zip) 내보내기(환경/설정/로그/캐시 요약)
- 작업 실패 시 상세 디버그 정보(`TaskResult.debug`) 확인

---

## 🚀 실행

### 1) 의존성 설치

```bash
pip install PyQt6 torch langchain langchain-huggingface langchain-community faiss-cpu python-docx pypdf olefile charset-normalizer
```

> GPU 사용 시 `faiss-cpu` 대신 `faiss-gpu` 사용 가능

### 2) 앱 실행

```bash
python "사내 규정검색기 v9 PyQt6.py"
```

기존 한국어 엔트리 파일은 **호환 래퍼**이며, 내부적으로 `regfinder.app_main.main()`을 호출합니다.

---

## 🧱 코드 구조 (모듈 분할 적용)

리팩토링 전 단일 파일 구조를 `regfinder` 패키지로 분리했습니다.

| 모듈 | 책임 |
|---|---|
| `regfinder/app_types.py` | 설정/Enum/데이터 클래스(`AppConfig`, `TaskResult`, `FileInfo` 등) |
| `regfinder/runtime.py` | 동적 import, 로깅, 경로 정책(data/models/logs/config/history) |
| `regfinder/file_utils.py` | 파일 읽기/메타/열기/크기 포맷 |
| `regfinder/bm25.py` | BM25Light 키워드 검색 |
| `regfinder/document_extractor.py` | TXT/DOCX/PDF/HWP 추출 |
| `regfinder/qa_system.py` | 인덱싱/캐시/검색/진단의 핵심 서비스 |
| `regfinder/workers.py` | QThread 워커(`ModelLoader/Search/DocumentProcessor/Download`) |
| `regfinder/ui_style.py` | QSS 스타일(`DARK_STYLE`) |
| `regfinder/ui_components.py` | UI 컴포넌트(`ResultCard`, `ProgressDialog` 등) |
| `regfinder/main_window.py` | 메인 윈도우/탭/이벤트 흐름 |
| `regfinder/app_main.py` | 앱 엔트리(`main`) |

---

## 📁 현재 파일 구조

```text
Internal-Regulations-Finder-main/
├── 사내 규정검색기 v9 PyQt6.py          # 호환 래퍼 엔트리
├── 사내 규정검색기 v9 PyQt6.spec        # PyInstaller onefile 설정
├── README.md
├── claude.md
├── gemini.md
├── regfinder/
│   ├── __init__.py
│   ├── app_types.py
│   ├── runtime.py
│   ├── file_utils.py
│   ├── bm25.py
│   ├── document_extractor.py
│   ├── qa_system.py
│   ├── workers.py
│   ├── ui_style.py
│   ├── ui_components.py
│   ├── main_window.py
│   └── app_main.py
├── tools/
│   ├── symbol_inventory.py               # 심볼 인벤토리/비교
│   └── smoke_refactor.py                 # 정적+import+sanity 스모크
├── docs/
│   ├── refactor_mapping.md
│   └── refactor_checklist.md
└── artifacts/
    ├── symbols_before.json
    └── symbols_after.json
```

---

## 📦 EXE 빌드

```bash
pip install pyinstaller
pyinstaller "사내 규정검색기 v9 PyQt6.spec"
```

출력: `dist/사내 규정검색기 v9.3_onefile.exe`

### spec 점검 포인트

- 진입 스크립트는 기존과 동일: `Analysis(['사내 규정검색기 v9 PyQt6.py'])`
- 분할된 패키지 인식을 위해 `pathex`에 프로젝트 루트 포함
- `regfinder.*` 모듈 hidden import 명시
- 기존 동적 import 대상(LangChain/HuggingFace/FAISS 등) hidden import 유지

---

## ✅ 누락 방지 검증

### 심볼 비교

```bash
python tools/symbol_inventory.py --paths regfinder "사내 규정검색기 v9 PyQt6.py" --out artifacts/symbols_after.json --compare-before artifacts/symbols_before.json --compare-after artifacts/symbols_after.json
```

### 스모크 검증

```bash
python tools/smoke_refactor.py
```

검증 항목:

- `py_compile` 전체 통과
- 분할 전/후 심볼 누락 0
- 모듈 import 통과
- 핵심 객체 생성 및 기본 sanity 체크 통과

---

## ⚙️ 데이터 저장 정책

- 우선 실행 폴더(포터블) 저장
- 실행 폴더가 쓰기 불가이면 사용자 경로(`LOCALAPPDATA`/`APPDATA`)로 폴백
- 적용 대상: `config.json`, `search_history.json`, `logs/`, `models/`

---

## 🧪 알려진 제한

- 이미지 기반 PDF는 텍스트 추출 불가
- 암호화 PDF는 비밀번호 입력 UI 미지원
- HWP 처리는 `olefile` 설치 필요

---

## 📄 라이선스

내부 사용 전용
