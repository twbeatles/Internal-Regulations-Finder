# 🤖 Gemini AI Guidelines: 사내 규정 검색기 v9.3

## 핵심 상태

- 단일 스크립트 구조 → `regfinder` 패키지 → 기능별 하위 패키지 구조로 분리 완료
- 현재 구현 패키지 경계:
  - `regfinder/core`: 타입/설정/런타임/파일 유틸
  - `regfinder/storage`: 설정/북마크/히스토리/텍스트 캐시/모델 인벤토리
  - `regfinder/documents`: TXT/DOCX/PDF/HWP/HWPX 추출과 선택형 OCR
  - `regfinder/search`: 검색 정규화/BM25/QA 시스템/진단
  - `regfinder/ui`: 메인 윈도우/UI 빌더/위젯/스타일
  - `regfinder/application`: 앱 엔트리/QThread 워커/WorkerRegistry
- 기존 `regfinder.qa_system`, `regfinder.main_window` 등 public import 경로는 호환 래퍼로 유지
- 워커 관리는 `WorkerRegistry`로 통합
- 설정은 `ConfigManager`(schema_version=4) 기반으로 마이그레이션 및 잘못된 값 복구 처리
- 캐시는 `CACHE_SCHEMA_VERSION=4` 기준으로 텍스트(SQLite)와 모델별 벡터 캐시로 분리
- 텍스트 캐시 파일 메타는 fingerprint까지 저장해 same-size modified file도 stale cache 없이 판별
- 텍스트 캐시는 chunk별 `page_start`, `page_end` page metadata를 저장할 수 있음
- 정적 분석 기준은 `pyrightconfig.json`으로 고정
- `pyrightconfig.json` / `.vscode/settings.json`은 optional dependency missing-import 잡음을 억제하고 내부 타입 오류를 우선 노출
- frozen(onefile) 모델 다운로드는 subprocess 대신 in-process 경로 사용
- frozen(onefile) 다운로드 취소는 현재 모델 완료 후 중단될 수 있음
- 오프라인 임베딩 런타임은 `Pillow` / `scikit-learn` / `sentence_transformers` 사전검증 추가
- `FileUtils.safe_read()`는 `UTF-8 -> CP949 -> EUC-KR` fast path 후 lazy `charset_normalizer` fallback 사용
- 모델을 아직 로드하지 않은 상태에서도 폴더를 먼저 불러와 `bm25_only` 초기 인덱스를 만들 수 있음
- 검색 정규화는 `regfinder.search.text`로 통합되어 BM25/필터/하이라이트가 같은 규칙을 사용
- 무공백 한국어 질의와 조사 제거 기반 semantic matching을 지원
- 검색 결과는 파일 단위로 그룹화되며 `match_count`, `snippet_chunk_idx`를 함께 유지
- 검색 결과는 `matched_chunk_indices`, `matched_doc_ids`까지 유지해 상세 보기에서 근거 청크 이동 가능
- 벡터 인덱스 실패 시에도 GUI에서 `bm25_only` 검색 모드로 계속 검색 가능
- 수정 파일 재추출 실패 시 기존 텍스트/청크는 현재 인덱스에서 제거되어 stale 검색 결과를 막음
- 암호화 PDF는 폴더 로드 전 사전 검사 후 파일별 비밀번호를 세션 메모리로 재사용
- 폴더 스캔 중 권한 없는 하위 폴더는 전체 실패 대신 제외 목록으로 수집하고 UI에 안내
- HWPX는 ZIP/XML 기반으로 본문 추출
- PDF는 page 단위 segment를 만들고 결과/상세/내보내기에서 page 범위를 표시
- OCR 설정(`PDF OCR 보강 사용`, `혼합 PDF의 빈 페이지도 OCR 보강`, Tesseract 경로/언어)은 config에 저장되고 mixed/image PDF 보강에 반영
- Tesseract OCR은 선택형이며 `pytesseract`, `PyMuPDF(fitz)`, 외부 Tesseract 실행 파일/언어 데이터가 없으면 OCR 없이 계속 동작
- 폴더 로드 취소/실패 시 이전 인덱스 상태를 복구해 current folder/file_infos/documents가 섞이지 않도록 정리
- 벡터 인덱싱 취소는 일반 실패와 분리해 `DOCS_CANCELED`로 반환
- BM25-only 인덱스 상태에서 모델 로드 성공 시 같은 worker 흐름에서 벡터 캐시 생성을 시도해 하이브리드 모드로 승격
- 검색 히스토리는 query 단독이 아니라 전체 검색 조건 기준으로 dedup
- 검색 결과/북마크 CSV 내보내기는 `csv` writer 기반 escaping을 사용
- 캐시 삭제 시 메모리 상태/결과/진단/PDF 비밀번호 세션을 함께 초기화
- 진단 탭/내부 상태는 `search_mode`, `vector_ready`, `memory_warning`, `vector_limit_reached`, 텍스트 캐시 경로/파일 수/청크 수를 표시
- 진단 ZIP은 기본적으로 `text_cache.sqlite` 원문 캐시를 제외하고, 사용자가 명시적으로 체크한 경우에만 포함
- 모델 다운로드 상태는 Hugging Face snapshot metadata와 가중치 파일 존재를 함께 확인해 판별
- 모델 다운로드 상태/용량은 `model_inventory.json` 캐시를 통해 재스캔 비용을 줄임
- 모델 다운로드 상태 접근은 `ModelDownloadState` 타입 계약으로 고정되어 Pylance 추론이 흔들리지 않음
- `.vscode/settings.json`과 `tests/test_repo_text_encoding.py`로 UTF-8/워크스페이스 진단 재발을 방지

## 현재 사용자 기능

- 검색 필터: 확장자/파일명/경로
- 검색 정렬: 점수순/파일명순/최근 수정순
- 파일 단위 검색 결과, 대표 청크, 근거 청크 수 표시
- 검색 중 기존 결과 유지 + 인라인 진행 카드/취소 + 적용 필터/정렬/모드 표시
- 무결과 시 필터 요약과 `필터 초기화` 액션 표시
- 히스토리 선택 시 조건 전체 복원 후 즉시 재검색
- 결과 상세 모달에서 파일 열기/경로 복사/근거 청크 이동/전체 문서 보기 제공
- 랭킹 점수 툴팁(상대 점수 + 벡터/키워드 구성요소)
- 암호화 PDF 사전 비밀번호 입력(세션 메모리만 사용)
- 결과 북마크 저장/내보내기
- 최근 폴더 다중 관리
- 진단 탭(인덱스 상태 + 검색 로그 요약 + 마지막 검색 통계)
- 오류 코드별 가이드 메시지
- 검색 후 검색어 유지 옵션
- 경로 필터 슬래시 정규화(`/`, `\`)
- 다운로드 실패 시 `op_id`와 실제 import 실패 패키지명을 함께 노출
- 모델만 로드된 상태에서는 검색 패널 비활성화, 폴더 인덱스가 준비된 뒤에만 검색 가능
- 설정창 모델 목록은 다운로드 완료 모델을 상단 우선 정렬
- 동일 폴더에서 모델만 바뀌면 텍스트 재추출 없이 벡터 캐시만 재생성
- 대규모 인덱스는 hard fail 대신 경고만 표시
- 대용량 폴더 로드 전 파일 수/총 크기/단일 파일 크기 경고를 표시하고 사용자가 계속 진행할 수 있음
- 파일/북마크 숫자 컬럼은 숫자 기준 정렬
- 폰트 슬라이더는 현재 표시 중인 결과 카드에 즉시 반영
- PDF 결과는 페이지 metadata가 있을 때 결과 카드/상세/내보내기에 표시
- 필터가 있는 벡터 검색은 최대 1000개 fetch 상한을 두고 한도 도달 여부를 진단에 기록
- BM25 후보도 파일 단위 결과 수가 채워질 때까지 후보 청크를 확장

## 운영 규칙

1. 워커 `run()`에서 UI 직접 변경 금지
2. 시그널 기반으로만 UI 업데이트
3. 검색/인덱스 상태는 `RegulationQASystem` public API를 통해 조회
4. 종료 시 워커 취소 및 리소스 정리
5. 추적 텍스트 파일은 `.editorconfig`, `.gitattributes` 기준으로 `UTF-8(no BOM)` / `LF` 유지
6. PyInstaller 경량화 시 `PIL` / `Pillow` / `scikit-learn` / `charset_normalizer` / 선택형 OCR 모듈 제외 여부를 먼저 검토
7. 로컬 테스트/로그/캐시 산출물(`.pytest_localappdata/`, `.regfinder_logs/`, SQLite sidecar, diagnostics zip)은 `.gitignore`로만 관리하고 커밋하지 않음
8. 앱 종료 시 cancel 요청만 보내고 바로 registry를 비우지 말고, 가능한 범위에서 worker 종료를 기다린 뒤 정리
9. `regfinder/*.py` compatibility wrapper는 기존 외부 import와 테스트 monkeypatch 경로를 유지하기 위한 API 표면이므로 제거하지 않음

## 검증 명령

```bash
python -m pyright .
python tools/smoke_refactor.py
python tools/benchmark_performance.py
python -m py_compile "사내 규정검색기 v9.spec"
python -m unittest discover -s tests -v
python -m pytest -q
```

- 2026-04-28 기준 `python -m pyright .` 0 errors
- 2026-04-28 기준 spec은 compatibility modules와 feature package implementation modules를 함께 hiddenimports에 포함

<!-- SPECKIT-AGENT-GUIDE:START -->

## Spec Kit / Spec-Driven Development (AI 에이전트 필독)

> 이 블록은 GitHub Spec Kit 활성화 및 기능 명세 작업 결과를 AI 에이전트가 바로 쓰도록 정리한 안내입니다.
> 수정 시 마커 주석을 유지하세요. 스크립트/후속 세션이 이 구간을 갱신합니다.

### 이 저장소 상태

- **프로젝트**: `Internal-Regulations-Finder`
- **Spec Kit 초기화**: `.specify/ 있음`
- **에이전트 스킬**: Grok=True, Claude=True, Codex/Agy(.agents)=True
- **활성 기능**: 아직 `specs/` 기능 명세 없음 — `.specify/` 만 준비된 상태

### 에이전트가 먼저 읽을 파일

1. `.specify/` 및 `.grok/skills` / `.claude/skills` / `.agents/skills` 의 `speckit-*`
2. 기능 작업 시작 시 `/speckit-specify` 로 `specs/00N-...` 생성

### 권장 워크플로 (스킬 / 슬래시 커맨드)

| 단계 | 커맨드 (Grok/Claude 등) | 산출 |
|------|-------------------------|------|
| 원칙 | `/speckit-constitution` | `.specify/memory/constitution.md` |
| 명세 | `/speckit-specify` | `specs/<id>/spec.md` |
| 계획 | `/speckit-plan` | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` |
| 작업 | `/speckit-tasks` | `tasks.md` |
| 구현 | `/speckit-implement` | 코드 (tasks 순서) |
| 갭점검 | `/speckit-converge` | `tasks.md` 에 Phase Convergence **append-only** |

- Codex skills 모드: `$speckit-specify` 형태일 수 있음
- 스킬 파일: `.grok/skills/speckit-*/SKILL.md`, `.claude/skills/speckit-*/SKILL.md`

### 작업 규칙 (에이전트)

1. **새 기능/큰 변경 전** 활성 `spec.md`·`tasks.md` 를 읽고, 없으면 specify→plan→tasks 순으로 만든다.
2. **구현은 tasks.md 체크리스트**를 따른다. 완료 시 `- [ ]` → `- [x]`.
3. **`/speckit-converge` 는 tasks.md 를 rewrite 하지 않는다** — 잔여 갭만 하단 Phase 로 append.
4. brownfield 프로젝트는 상당 기능이 이미 있을 수 있다. 중복 구현 전에 코드·`[x]` 태스크를 확인한다.
5. 웹/데스크톱 패리티 등 **out-of-scope Assumptions** 는 새 feature 로 분리하는 것을 선호한다.
6. 기본 integration 은 **grok** 이며, 동일 레포에 claude / codex / agy 스킬도 multi-install 되어 있을 수 있다.

### 관련 링크

- Spec Kit: https://github.com/github/spec-kit
- 로컬 CLI: `specify` (uv tool, 버전은 `specify version`)

<!-- SPECKIT-AGENT-GUIDE:END -->
