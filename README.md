# 📚 사내 규정 검색기 v9.3

> 로컬 AI 기반 사내 규정 문서 검색 프로그램
> PyQt6 GUI | 하이브리드 검색(Vector + BM25) | 분리 캐시(Text + Vector) | 오프라인 모델 지원

---

## ✨ 핵심 기능

- 하이브리드 검색 + 자동 검색 모드 전환
  - 벡터 인덱스가 준비되면 `하이브리드` 또는 `벡터` 모드로 검색
  - 벡터 인덱스 생성/로드에 실패해도 `키워드(BM25)` 모드로 계속 검색 가능
- 한국어 규정명 친화 검색
  - 공용 검색 정규화(`regfinder/search_text.py`)로 BM25, 필터, 하이라이트 규칙 통일
  - 무공백 질의(`휴가규정`, `인사규정`)와 조사 포함 질의(`휴가를`) 대응
  - 경로 필터는 `/`, `\` 입력을 동일하게 처리
- 파일 단위 결과 그룹화
  - 검색 결과는 청크가 아니라 파일 단위로 집계
  - 대표 청크 snippet, `근거 청크 n개`, `대표 청크 #n` 표시
  - 결과 점수는 퍼센트형 유사도가 아니라 상대적 `랭킹 점수`
- 검색 UX / 운영 가시성
  - 검색 필터(확장자/파일명/경로), 정렬(랭킹점수/파일명/최근 수정)
  - 검색 결과 하이라이트, 검색 시간, 검색 모드 표시, TXT/CSV 내보내기
  - 검색 후 검색어 유지 옵션, 대규모 인덱스 경고, 진단 탭 제공
- 캐시 / 성능
  - 증분 인덱싱 및 분리 캐시(텍스트 SQLite + 모델별 벡터 캐시)
  - 동일 폴더에서 모델만 바뀌면 텍스트 캐시 재사용
  - 필터 검색 시 적중 파일을 찾을 때까지 벡터 후보를 확장 fetch하여 거짓 음성 감소
- 문서 처리 / 배포
  - 암호화 PDF 비밀번호 입력(세션 메모리 재사용, 디스크 저장 안 함)
  - OCR 인터페이스 확장 포인트 제공(기본 엔진 미포함)
  - 오프라인 모델 선택 다운로드(취소 지원)
  - EXE(onefile) 환경 오프라인 모델 다운로드 경로 지원

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
- `.vscode/settings.json`으로 VSCode의 workspace Pylance 범위와 Windows 터미널 UTF-8 Python 출력을 고정
- `ModelDownloadState` 타입 계약과 `tests/test_repo_text_encoding.py` 회귀 테스트로 모델 상태 추론/인코딩 검증을 고정
- PyInstaller spec은 `pytest`, `pyright` 같은 개발 전용 도구를 번들에서 제외
- PyInstaller onefile 번들은 오프라인 모델 다운로드와 lazy 인코딩 fallback, 검색 정규화 helper를 위해 필요한 런타임 모듈을 포함

---

## 🧱 코드 구조

| 모듈 | 책임 |
|---|---|
| `regfinder/app_types.py` | 설정/Enum/데이터 클래스 |
| `regfinder/runtime.py` | 로깅, 경로 정책, op_id |
| `regfinder/persistence.py` | 설정 스키마(v3), 북마크/최근폴더/검색로그 저장 |
| `regfinder/model_inventory.py` | 다운로드 모델 상태/용량 캐시 |
| `regfinder/worker_registry.py` | 작업 종류별 워커 레지스트리 |
| `regfinder/file_utils.py` | 파일 읽기/발견(scandir)/메타/열기/크기 포맷 |
| `regfinder/document_extractor.py` | TXT/DOCX/PDF/HWP 추출(+PDF 비밀번호/OCR 훅) |
| `regfinder/text_cache.py` | 텍스트 캐시(SQLite) |
| `regfinder/search_text.py` | 공용 검색 정규화/토큰화/필터 매칭 helper |
| `regfinder/bm25.py` | BM25Index 검색 |
| `regfinder/qa_system.py` | 인덱싱/검색/텍스트 캐시+벡터 캐시 핵심 |
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
python -m pyright .
python tools/smoke_refactor.py
python tools/benchmark_performance.py
python -m py_compile "사내 규정검색기 v9 PyQt6.spec"
python -m unittest discover -s tests -v
python -m pytest -q
```

- 기준선: `python -m pyright .` 0 errors
- 추적 텍스트 파일은 `UTF-8(no BOM)` 기준 유지
- Windows PowerShell/Python 출력에서 한글이 깨져 보여도 실제 UTF-8 파일 손상과는 별개일 수 있음
- 최근 회귀 포인트
  - 공용 검색 정규화(`search_text.py`)
  - 무공백 한국어 질의 / 조사 제거
  - 파일 단위 결과 집계(`match_count`, `snippet_chunk_idx`)
  - BM25-only fallback, `search_mode`, `vector_ready`, `memory_warning`
  - `keep_search_text` 설정 마이그레이션
  - 랭킹 점수 UI/북마크/내보내기 wording

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
- `charset_normalizer`는 `FileUtils.safe_read()` fallback 경로에서 동적 import되므로 hidden import 유지 필요
- `regfinder.search_text`는 검색 정규화 helper로서 spec hidden import 목록에도 반영
- 모델 다운로드 완료 여부는 `models/models--<org>--<name>/{blobs,snapshots}` 캐시 구조 기준으로 판별
- 현재 onefile 크기는 `torch` / `faiss` / `PyQt6` 포함으로 인해 약 300MB 수준

---

## ⚙️ 데이터 저장 정책

- 포터블 경로 우선, 불가 시 `LOCALAPPDATA/APPDATA` 폴백
- 저장 항목:
  - `config.json` (schema_version=3)
  - `search_history.json`
  - `bookmarks.json`
  - `recent_folders.json`
  - `search_log.json`
  - `model_inventory.json`
  - `logs/`, `models/`
- 텍스트/벡터 캐시는 사용자 설정 경로가 아니라 시스템 임시 경로 하위의 `reg_qa_v93/` 아래에 저장
  - `text/<folder_hash>/text_cache.sqlite`
  - `vector/<folder_hash>/<model_hash>/`

---

## 🧪 알려진 제한

- 이미지 PDF는 기본 OCR 엔진이 미포함이라 별도 엔진 연결 전에는 텍스트 추출 불가
- 암호화 PDF는 올바른 비밀번호가 필요
- HWP는 문서 형식 손상/변형에 따라 추출 실패 가능
- 오프라인 모델 다운로드는 최초 1회 인터넷 연결이 필요
- 대규모 인덱스는 hard fail 대신 경고만 표시하므로 메모리 사용량은 환경에 따라 커질 수 있음

---

## 📄 라이선스

내부 사용 전용
