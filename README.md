# 📚 사내 규정 검색기 v9.3

> 로컬 AI 기반 사내 규정 문서 검색 프로그램
> PyQt6 GUI | 하이브리드 검색(Vector + BM25) | 증분 인덱싱 | 오프라인 모델 지원

---

## ✨ 핵심 기능

- 하이브리드 검색(벡터 70% + BM25 30%)
- 검색 필터(확장자/파일명/경로), 정렬(점수/파일명/최근 수정)
- 결과 카드 하이라이트, 검색 시간 표시, TXT/CSV 내보내기
- 북마크 저장/조회/내보내기
- 최근 폴더 다중 관리
- 증분 인덱싱/캐시(변경 파일만 재처리)
- 암호화 PDF 비밀번호 입력(세션 메모리 재사용, 디스크 저장 안 함)
- OCR 인터페이스 확장 포인트 제공(기본 엔진 미포함)
- 오프라인 모델 선택 다운로드(취소 지원)
- EXE(onefile) 환경 오프라인 모델 다운로드 경로 지원
- 모델 로드 완료 직후 검색 입력창 즉시 활성화
- 설정창에서 다운로드 완료 모델 우선 정렬/선택 및 상태 표시
- 진단 탭(인덱스 상태 + 검색 로그 요약) 및 진단 ZIP 내보내기
- 오류 코드별 가이드 메시지 + 상세 디버그(`TaskResult.debug`)
- 다운로드/모델 로드 전 `Pillow` / `scikit-learn` / `sentence_transformers` 런타임 사전검증

---

## 🚀 실행

### 1) 의존성 설치

```bash
pip install PyQt6 torch sentence-transformers scikit-learn pillow langchain-huggingface langchain-community langchain-text-splitters langchain-core faiss-cpu python-docx pypdf olefile charset-normalizer
```

### 2) 앱 실행

```bash
python "사내 규정검색기 v9 PyQt6.py"
```

기존 한국어 엔트리 파일은 호환 래퍼이며 내부적으로 `regfinder.app_main.main()`을 호출합니다.

---

## 🧪 개발 품질 기준

- `pyrightconfig.json`을 저장소 기준 Pylance/Pyright 설정으로 사용
- 기준 타입 체크 레벨: `pythonVersion = 3.14`, `typeCheckingMode = standard`
- `.editorconfig` + `.gitattributes`로 추적 텍스트 파일의 `UTF-8(no BOM)`, `LF`, final newline 정책을 고정
- PyInstaller spec은 `pytest`, `pyright` 같은 개발 전용 도구를 번들에서 제외
- PyInstaller onefile 번들은 오프라인 모델 다운로드를 위해 `sentence_transformers`, `scikit-learn`, `Pillow` 메타데이터/런타임을 포함

---

## 🧱 코드 구조

| 모듈 | 책임 |
|---|---|
| `regfinder/app_types.py` | 설정/Enum/데이터 클래스 |
| `regfinder/runtime.py` | 로깅, 경로 정책, op_id |
| `regfinder/persistence.py` | 설정 스키마(v2), 북마크/최근폴더/검색로그 저장 |
| `regfinder/worker_registry.py` | 작업 종류별 워커 레지스트리 |
| `regfinder/file_utils.py` | 파일 읽기/메타/열기/크기 포맷 |
| `regfinder/document_extractor.py` | TXT/DOCX/PDF/HWP 추출(+PDF 비밀번호/OCR 훅) |
| `regfinder/bm25.py` | BM25Light 검색 |
| `regfinder/qa_system.py` | 인덱싱/검색/캐시 핵심 |
| `regfinder/qa_system_mixins.py` | 진단/상태 조회 API |
| `regfinder/workers.py` | QThread 워커 |
| `regfinder/ui_components.py` | ResultCard/ProgressDialog 등 |
| `regfinder/ui_style.py` | QSS 스타일 |
| `regfinder/main_window.py` | 메인 이벤트 오케스트레이션 |
| `regfinder/main_window_ui_mixin.py` | UI 빌더 메서드 |
| `regfinder/main_window_mixins.py` | 설정/진단/북마크 보조 로직 |
| `regfinder/app_main.py` | 앱 엔트리 |

---

## ✅ 검증

```bash
pyright .
python tools/smoke_refactor.py
python -m py_compile "사내 규정검색기 v9 PyQt6.spec"
python -m unittest discover -s tests -v
pytest -q
```

- 기준선: `pyright .` 0 errors
- 추적 텍스트 파일은 `UTF-8(no BOM)` 기준 유지
- 최근 회귀 포인트: 로깅 `op_id` 충돌, frozen 모델 다운로드 초기화, `Pillow`/`scikit-learn`/`sentence_transformers` import 검증

---

## 📦 EXE 빌드

```bash
pip install pyinstaller
pyinstaller "사내 규정검색기 v9 PyQt6.spec"
```

출력: `dist/사내 규정검색기 v9.3_onefile.exe`

추가 메모:

- onefile EXE는 `sys.executable -c` 서브프로세스 대신 in-process 다운로드 경로를 사용
- `transformers`가 `PIL.Image`를 모듈 초기화 시 참조하므로, 경량화 시 `Pillow` 제외 금지
- 모델 다운로드 완료 여부는 `models/models--<org>--<name>/{blobs,snapshots}` 캐시 구조 기준으로 판별
- 현재 onefile 크기는 `torch` / `faiss` / `PyQt6` 포함으로 인해 약 300MB 수준

---

## ⚙️ 데이터 저장 정책

- 포터블 경로 우선, 불가 시 `LOCALAPPDATA/APPDATA` 폴백
- 저장 항목:
  - `config.json` (schema_version=2)
  - `search_history.json`
  - `bookmarks.json`
  - `recent_folders.json`
  - `search_log.json`
  - `logs/`, `models/`

---

## 🧪 알려진 제한

- 이미지 PDF는 기본 OCR 엔진이 미포함이라 별도 엔진 연결 전에는 텍스트 추출 불가
- 암호화 PDF는 올바른 비밀번호가 필요
- HWP는 문서 형식 손상/변형에 따라 추출 실패 가능
- 오프라인 모델 다운로드는 최초 1회 인터넷 연결이 필요하며, 실패 시 오류창의 `op_id`와 실제 import 실패 패키지명을 함께 확인하는 것이 우선

---

## 📄 라이선스

내부 사용 전용
